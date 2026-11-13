"""Harness^2 core: harness trees, probe profiles, probe runs, library.

Mechanical half of the loop. The LLM half (editor, composer, selector,
reflector) runs in the host agent's own session, guided by the plugin's
bundled skills; this module is deterministic and side-effect limited to:

- the plugin data directory (runs/, candidates/, library/), which survives
  plugin updates and follows the active profile;
- Hermes probe profiles named harness2-* (created once by the standard
  ``hermes profile create --clone`` mechanism, which carries the active
  profile's config and .env under hermes' own clone policy, and refreshed on
  each probe by applying the tree's overlay keys through
  ``hermes -p <probe-profile> config set`` plus replacing SOUL.md / skills/);
- spawning ``hermes -p <probe-profile> chat`` one-shot sessions (the probes).

The installed plugin tree itself is never written to.

YAML goes through PyYAML (declared in plugin.yaml as
``python_dependencies`` and installed at plugin install time); hosts
without PyYAML (the docker-managed venv ships ruamel.yaml instead) fall
back to a minimal ruamel shim defined below.
"""
from __future__ import annotations

import difflib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

try:
    import yaml  # PyYAML, declared in plugin.yaml (python_dependencies); installed at plugin install
except ModuleNotFoundError:  # docker-managed venv ships ruamel.yaml, not PyYAML
    import io as _io

    from ruamel.yaml import YAML as _RuamelYAML
    from ruamel.yaml.error import YAMLError as _RuamelYAMLError

    class _RuamelYamlShim:
        """Minimal PyYAML-compatible surface (the only calls core.py makes).

        ruamel preserves mapping insertion order by default; the only
        sort_keys call site in core.py passes sort_keys=False, so output
        matches PyYAML's behavior here.
        """

        YAMLError = _RuamelYAMLError

        @staticmethod
        def safe_load(stream):
            return _RuamelYAML(typ="safe", pure=True).load(stream)

        @staticmethod
        def safe_dump(data, sort_keys=True):
            y = _RuamelYAML(typ="safe", pure=True)
            y.default_flow_style = False  # PyYAML-like block style
            buf = _io.StringIO()
            y.dump(data, buf)
            return buf.getvalue()

    yaml = _RuamelYamlShim()

PLUGIN_NAME = "harness2"
KEEP_BASE = "KEEP_BASE"
MAX_CONTEXT_CHARS = 20_000
PROBE_GRACE_SECONDS = 180  # startup + teardown headroom on top of the run budget

TASK_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,31}$")


class H2Error(ValueError):
    """User-facing error; the message is safe to return to the model."""


# ---------------------------------------------------------------------------
# Roots and executables


def data_root() -> Path:
    """Plugin-owned state root (profile-scoped, survives updates)."""
    from plugins.plugin_storage import plugin_data_dir

    root = Path(plugin_data_dir(PLUGIN_NAME))
    root.mkdir(parents=True, exist_ok=True)
    return root


def assets_dir() -> Path:
    return Path(__file__).resolve().parent / "assets"


def base_tree() -> Path:
    p = assets_dir() / "base"
    if not (p / "SOUL.md").exists():
        raise H2Error("base harness asset missing (assets/base/SOUL.md); install is incomplete")
    return p


def prompts_dir() -> Path:
    p = assets_dir() / "prompts"
    if not p.is_dir():
        raise H2Error("stage prompts asset missing (assets/prompts/); install is incomplete")
    return p


def runs_dir() -> Path:
    d = data_root() / "runs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def candidates_dir() -> Path:
    d = data_root() / "candidates"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _hermes_home() -> Path:
    """Home of the active profile (its config.yaml, .env and skills/ live here)."""
    try:
        from hermes_constants import get_hermes_home

        return Path(get_hermes_home())
    except Exception:  # noqa: BLE001 - tests and direct use without the hermes core
        return Path(os.environ.get("HERMES_HOME") or (Path.home() / ".hermes"))


def _hermes_root() -> Path:
    """Root that owns the profiles/ directory for the active profile."""
    try:
        from hermes_constants import get_default_hermes_root

        return Path(get_default_hermes_root(home=_hermes_home()))
    except Exception:  # noqa: BLE001 - tests and direct use without the hermes core
        return _hermes_home()


def _profile_dirs() -> Path:
    """Directory holding probe profile dirs (harness2-*)."""
    return _hermes_root() / "profiles"


def _run_hermes(args, timeout: int, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [_hermes_exe()] + list(args),
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )


def _hermes_exe() -> str:
    exe = shutil.which("hermes")
    if exe:
        return exe
    cand = Path(sys.executable).resolve().parent / "hermes"
    if cand.exists():
        return str(cand)
    raise H2Error("hermes executable not found on PATH; probes cannot run")


# ---------------------------------------------------------------------------
# Tasks and candidate trees


def task_dir(task: str) -> Path:
    if not TASK_RE.match(task or ""):
        raise H2Error(f"invalid task slug {task!r}: use lowercase [a-z0-9-], 1-64 chars")
    return runs_dir() / task


def _validate_source_dir(raw: str) -> Path:
    """Resolve and refuse a model-named source_dir that could leak secrets.

    A full-tool probe agent reads the copied material, so the source must
    live under the session's working directory and must not pass through
    the Hermes home/root (config.yaml, .env, state.db), a credential dir
    under the OS home, or any dot-dir.
    """
    p = Path(raw).expanduser()
    if not p.is_dir():
        raise H2Error(f"source_dir not found: {p}")
    try:
        resolved = p.resolve()
    except OSError:
        raise H2Error(f"source_dir not found: {p}")
    cwd = Path(os.getcwd()).resolve()
    if not resolved.is_relative_to(cwd):
        raise H2Error(
            f"source_dir {p} is outside the session's working directory {cwd}; "
            "only directories under the working directory may be copied into probe workspaces"
        )
    blocked: dict[str, Path] = {
        "the Hermes home": _hermes_home().expanduser(),
        "the Hermes root": _hermes_root().expanduser(),
    }
    home = Path.home()
    for name in ("ssh", "aws", "gnupg", "kube", "docker"):
        blocked[f"credential dir {home}/{name}"] = home / name
    for label, base in blocked.items():
        try:
            resolved.relative_to(base)
        except ValueError:
            continue
        raise H2Error(f"source_dir {p} is inside {label} ({base}); refusing")
    for part in resolved.parts[1:]:
        if part.startswith("."):
            raise H2Error(f"source_dir {p} passes through a dot-dir ({part}); refusing")
    return resolved


def init_task(task: str, task_text: str, source_dir: str | None = None) -> dict:
    d = task_dir(task)
    if (d / "task.md").exists():
        raise H2Error(f"task already initialized: {d / 'task.md'} exists; pick another slug")
    text = (task_text or "").strip()
    if not text:
        raise H2Error("task_text is empty")
    d.mkdir(parents=True, exist_ok=True)
    (d / "task.md").write_text(text + "\n")
    if source_dir:
        src = _validate_source_dir(source_dir)
        dst = d / "source"
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
    (d / ".meta.json").write_text(
        json.dumps({"task": task, "created": int(time.time())}, indent=2) + "\n"
    )
    return {
        "task": task,
        "task_dir": str(d),
        "source_files": sorted(p.relative_to(d).as_posix() for p in (d / "source").rglob("*") if p.is_file())
        if (d / "source").is_dir()
        else [],
    }


def candidate_dir(task: str, cid: str) -> Path:
    if not TASK_RE.match(task or ""):
        raise H2Error(f"invalid task slug {task!r}")
    if not ID_RE.match(cid or ""):
        raise H2Error(f"invalid candidate id {cid!r}: use lowercase [a-z0-9-], 1-32 chars")
    return candidates_dir() / f"{task}-{cid}"


def resolve_tree(task: str, ref: str) -> Path:
    """Resolve 'base' | 'candidate:<id>' | 'library:<entry>' to a tree path."""
    ref = (ref or "").strip()
    if ref == "base":
        return base_tree()
    if ref.startswith("candidate:"):
        cid = ref.split(":", 1)[1]
        if not ID_RE.match(cid or ""):
            raise H2Error(
                f"invalid candidate id {cid!r} in {ref!r}: use lowercase [a-z0-9-], 1-32 chars"
            )
        p = candidates_dir() / f"{task}-{cid}"
    elif ref.startswith("library:"):
        entry = ref.split(":", 1)[1]
        if not TASK_RE.match(entry or ""):
            raise H2Error(
                f"invalid library entry {entry!r} in {ref!r}: use lowercase [a-z0-9-], 1-64 chars"
            )
        p = data_root() / "library" / "entries" / entry / "harness"
    else:
        raise H2Error("tree must be 'base', 'candidate:<id>' or 'library:<entry>'")
    if not (p / "SOUL.md").exists():
        raise H2Error(f"tree not found or has no SOUL.md: {p}")
    return p


def seed_candidate(task: str, cid: str, from_ref: str = "base", note: str = "") -> dict:
    dst = candidate_dir(task, cid)
    if dst.exists():
        raise H2Error(f"{dst.name} already exists; pick another id or delete it first")
    src = resolve_tree(task, from_ref)
    shutil.copytree(src, dst)
    (dst / ".meta.json").write_text(
        json.dumps({"task": task, "id": cid, "from": from_ref, "note": note}, indent=2) + "\n"
    )
    return {"candidate": str(dst), "name": dst.name, "from": from_ref}


# ---------------------------------------------------------------------------
# Probe profiles and probe runs


def profile_name(task: str, probe_id: str) -> str:
    name = f"harness2-{task}-{probe_id}".lower()
    return re.sub(r"-{2,}", "-", name).strip("-")


# ---------------------------------------------------------------------------
# Gateway platform-credential isolation: a probe profile must never run the
# gateway's adapters as a second consumer of the active profile's bot tokens
# (the multiplexer would stamp a fatal duplicate_credential verdict per
# platform and flip the desktop health pill, which ignores only
# disabled/not_configured states). That isolation belongs to hermes' own
# clone policy: ``hermes profile create --clone`` decides which credentials
# a second profile may carry and strips the source's bot-channel tokens. So
# this plugin copies no secret files at all - the clone carries the active
# profile's config and .env once, and every refresh after the first only
# applies overlay keys through ``hermes -p <profile> config set``.


def materialize_profile(tree: Path, profile: str, budget: int) -> Path:
    """Create-once / refresh-on-use materialization of a tree as a profile.

    First use: ``hermes profile create --clone <name>`` with HERMES_HOME
    pinned to the active profile's home, so the child can never clone from a
    different profile. The clone carries the active profile's config and
    .env once, under hermes' own clone policy. Every use: the tree's
    overlay keys and the run budget are applied one key at a time through
    ``hermes -p <profile> config set`` - the plugin never rewrites the
    profile's config.yaml or touches its .env - and SOUL.md and skills/ are
    replaced with the tree's.
    """
    home = _hermes_home()
    dst = _profile_dirs() / profile
    if not dst.exists():
        env = {**os.environ, "HERMES_HOME": str(home)}
        r = _run_hermes(["profile", "create", "--clone", profile], timeout=300, env=env)
        if r.returncode != 0 or not dst.exists():
            raise H2Error(
                f"hermes profile create --clone {profile} failed: "
                f"{(r.stderr or r.stdout).strip()[:500]}"
            )

    overlay_path = tree / "config.yaml"
    overlay = yaml.safe_load(overlay_path.read_text()) if overlay_path.exists() else None
    overlay = overlay if isinstance(overlay, dict) else {}
    for key, value in _flatten_config(overlay).items():
        _set_probe_config(profile, key, value)
    _set_probe_config(profile, "agent.run_budget_seconds", str(int(budget)))

    soul = tree / "SOUL.md"
    if soul.exists():
        shutil.copy2(soul, dst / "SOUL.md")

    skills_dst = dst / "skills"
    if skills_dst.exists():
        shutil.rmtree(skills_dst)
    skills_src = tree / "skills"
    skills = []
    if skills_src.is_dir():
        shutil.copytree(skills_src, skills_dst)
        skills = sorted(p.name for p in skills_dst.iterdir())
    return dst


def _set_probe_config(profile: str, key: str, value: str) -> None:
    """Apply one overlay key through the CLI; the profile's config.yaml stays
    owned by the clone that created it."""
    r = _run_hermes(["-p", profile, "config", "set", key, value], timeout=120)
    if r.returncode != 0:
        raise H2Error(
            f"hermes config set {key} failed for profile {profile}: "
            f"{(r.stderr or r.stdout).strip()[:300]}"
        )


def _flatten_config(cfg: dict) -> dict[str, str]:
    """Dotted leaf keys -> CLI value strings for ``hermes config set``
    (the CLI auto-coerces bools, ints and YAML/JSON literals)."""
    out: dict[str, str] = {}

    def walk(prefix: str, node: object) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                walk(f"{prefix}.{k}" if prefix else str(k), v)
        else:
            out[prefix] = _config_value_str(node)

    walk("", cfg)
    return out


def _config_value_str(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    if isinstance(value, (list, dict)):
        return json.dumps(value)
    return str(value)


def _final_reply(log: Path, limit: int = 400) -> str:
    text = ""
    if log.exists():
        for line in log.read_text(errors="replace").splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            if ev.get("type") == "result":
                text = ev.get("text") or ""
    return text.strip()[:limit]


def _deliverables(ws: Path) -> list[str]:
    out = ws / "out"
    if not out.is_dir():
        return []
    return sorted(p.relative_to(ws).as_posix() for p in out.rglob("*") if p.is_file())


def run_probe(task: str, tree_ref: str, probe_id: str, budget: int, source_tag: str) -> dict:
    """Materialize the tree as a profile and run one budgeted one-shot session."""
    if not ID_RE.match(probe_id or ""):
        raise H2Error(f"invalid probe id {probe_id!r}: use lowercase [a-z0-9-], 1-32 chars")
    tree = resolve_tree(task, tree_ref)
    tdir = task_dir(task)
    if not (tdir / "task.md").exists():
        raise H2Error(f"task not initialized: missing {tdir / 'task.md'} (call harness2_init)")

    profile = profile_name(task, probe_id)
    materialize_profile(tree, profile, budget)

    probe_dir = tdir / probe_id
    probe_dir.mkdir(parents=True, exist_ok=True)
    (probe_dir / ".meta.json").write_text(
        json.dumps(
            {"probe": probe_id, "profile": profile, "tree": tree_ref, "started": int(time.time())},
            indent=2,
        )
        + "\n"
    )
    ws = probe_dir / "ws"
    if ws.exists():
        shutil.rmtree(ws)
    (ws / "out").mkdir(parents=True)
    shutil.copy2(tdir / "task.md", ws / "task.md")
    if (tdir / "source").is_dir():
        shutil.copytree(tdir / "source", ws / "source")
    if (tree / "hermes.md").exists():
        shutil.copy2(tree / "hermes.md", ws / ".hermes.md")
    if (tree / "scripts").is_dir():
        shutil.copytree(tree / "scripts", ws / "scripts")
    skills_root = tree / "skills"
    if skills_root.is_dir():
        for d in skills_root.glob("*/scripts"):
            if d.is_dir():
                (ws / "scripts").mkdir(exist_ok=True)
                for f in d.iterdir():
                    if f.is_file():
                        shutil.copy2(f, ws / "scripts" / f.name)

    log = probe_dir / "stdout.log"
    cmd = [
        _hermes_exe(), "-p", profile, "chat",
        "--in", str(ws),
        "--query-file", str(ws / "task.md"),
        "--format", "stream-json",
        "--source", source_tag or "tool",
    ]
    started = time.time()
    exit_code = 0
    timed_out = False
    try:
        with open(log, "wb") as out:
            subprocess.run(
                cmd, stdout=out, stderr=subprocess.STDOUT,
                timeout=int(budget) + PROBE_GRACE_SECONDS,
            )
    except subprocess.TimeoutExpired:
        timed_out = True
        exit_code = -1
    duration = round(time.time() - started, 1)

    prof_sessions = _profile_dirs() / profile / "sessions"
    if prof_sessions.is_dir():
        newest = sorted(prof_sessions.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
        if newest:
            shutil.copy2(newest[0], probe_dir / "transcript.jsonl")

    return {
        "probe": probe_id,
        "profile": profile,
        "tree": tree_ref,
        "probe_dir": str(probe_dir),
        "workspace": str(ws),
        "trajectory": str(log),
        "exit_code": exit_code,
        "timed_out": timed_out,
        "duration_s": duration,
        "deliverables": _deliverables(ws),
        "final_reply": _final_reply(log),
    }


# ---------------------------------------------------------------------------
# Validation gate


def parse_frontmatter(text: str):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return None
    try:
        return yaml.safe_load(m.group(1))
    except yaml.YAMLError:
        return None


def check_tree(tree: Path) -> list[str]:
    """Structural gate: YAML parses, skill names/trigger lines/scripts resolve,
    context files under the size cap. Judgment rules are the editor's job."""
    errors: list[str] = []
    cfg = tree / "config.yaml"
    if cfg.exists():
        try:
            yaml.safe_load(cfg.read_text())
        except yaml.YAMLError as e:
            errors.append(f"config.yaml: invalid YAML: {e}")

    soul_p, hermes_p = tree / "SOUL.md", tree / "hermes.md"
    always_on = (
        (soul_p.read_text() if soul_p.exists() else "")
        + "\n"
        + (hermes_p.read_text() if hermes_p.exists() else "")
    )

    skills_root = tree / "skills"
    if skills_root.is_dir():
        for skill_md in sorted(skills_root.glob("*/SKILL.md")):
            name = skill_md.parent.name
            fm = parse_frontmatter(skill_md.read_text())
            if fm is None:
                errors.append(f"skills/{name}: SKILL.md frontmatter missing or invalid YAML")
                continue
            if fm.get("name") != name:
                errors.append(
                    f"skills/{name}: frontmatter name {fm.get('name')!r} != directory name"
                )
            if not re.search(rf"\b{re.escape(name)}\b", always_on):
                errors.append(f"skills/{name}: no trigger line in SOUL.md or hermes.md")
            for m in re.finditer(r"scripts/([\w.\-]+)", skill_md.read_text()):
                if not (skills_root / name / "scripts" / m.group(1)).exists():
                    errors.append(f"skills/{name}: names missing script scripts/{m.group(1)}")

    for p in (soul_p, hermes_p):
        if p.exists() and len(p.read_text()) > MAX_CONTEXT_CHARS:
            errors.append(f"{p.name}: {len(p.read_text())} chars, over the 20k cap")
    return errors


def check_candidate(task: str, cid: str) -> dict:
    tree = candidate_dir(task, cid)
    if not tree.is_dir():
        raise H2Error(f"candidate not found: {tree}")
    errors = check_tree(tree)
    return {"candidate": tree.name, "ok": not errors, "errors": errors}


def diff_tree_files(base: Path, other: Path) -> dict[str, str]:
    """File-level diff between two harness trees: name -> added/removed/changed."""

    def files(t: Path) -> dict[str, Path]:
        return {
            p.relative_to(t).as_posix(): p
            for p in t.rglob("*")
            if p.is_file() and p.name != ".meta.json"
        }

    fa, fb = files(base), files(other)
    out: dict[str, str] = {}
    for name in set(fa) | set(fb):
        if name not in fb:
            out[name] = "removed"
        elif name not in fa:
            out[name] = "added"
        elif fa[name].read_bytes() != fb[name].read_bytes():
            out[name] = "changed"
    return out


_LABEL = {"added": "added    ", "removed": "removed  ", "changed": "changed  "}


def diff_trees(base: Path, other: Path) -> list[str]:
    """File-level diff between two harness trees (added/removed/changed)."""
    return [_LABEL[s] + n for n, s in sorted(diff_tree_files(base, other).items())]


def _diff_text(a: str, b: str, label_a: str, label_b: str) -> str:
    out = difflib.unified_diff(
        a.splitlines(), b.splitlines(), fromfile=label_a, tofile=label_b, n=3, lineterm=""
    )
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------------------
# Improvement library


def library_entries_dir() -> Path:
    d = data_root() / "library" / "entries"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _regen_library_index() -> Path:
    entries = library_entries_dir()
    rows = [
        "# Improvement library index",
        "",
        "One row per entry. A future Propose/Probe/Compose session reads the index",
        "first and inspects an entry's harness/ and EXPERIENCE.md on demand.",
        "",
    ]
    for d in sorted(entries.iterdir()):
        if d.name.startswith("_") or not d.is_dir():
            continue
        cue = ""
        exp = d / "EXPERIENCE.md"
        if exp.exists():
            for line in exp.read_text(errors="replace").splitlines():
                if line.lower().startswith("cue:"):
                    cue = line.split(":", 1)[1].strip()
                    break
        if not cue:
            cue = "(see EXPERIENCE.md)"
        rows.append(f"- {d.name}/  |  {cue}")
    idx = entries.parent / "INDEX.md"
    idx.write_text("\n".join(rows) + "\n")
    return idx


def adopt(
    task: str,
    adopted_ref: str,
    experience_path: str | None = None,
    no_entry: bool = False,
) -> dict:
    """Bank an adopted harness (or KEEP_BASE) plus the reflector's experience."""
    entry = library_entries_dir() / task_dir(task).name
    if entry.exists():
        raise H2Error(f"library entry already exists for task {task!r}")
    entry.mkdir(parents=True)
    (entry / ".meta.json").write_text(
        json.dumps({"task": task, "adopted": adopted_ref, "no_entry": no_entry, "ts": int(time.time())}, indent=2) + "\n"
    )
    if adopted_ref == KEEP_BASE:
        pass
    else:
        if not adopted_ref.startswith("candidate:"):
            raise H2Error("adopted must be 'KEEP_BASE' or 'candidate:<id>'")
        tree = resolve_tree(task, adopted_ref)
        shutil.copytree(tree, entry / "harness")
        meta = entry / "harness" / ".meta.json"
        if meta.exists():
            meta.unlink()
    if no_entry:
        (entry / "EXPERIENCE.md").write_text(f"# Experience: {task}\n\nNO_ENTRY\n")
    else:
        if not experience_path:
            raise H2Error("experience_path (the reflection file) is required unless no_entry is set")
        p = Path(experience_path).expanduser()
        if not p.exists():
            raise H2Error(f"experience file not found: {p}")
        m = re.search(r"<experience>\n(.*?)\n</experience>", p.read_text(errors="replace"), re.S)
        if not m:
            raise H2Error("no <experience> block found in the reflection file")
        (entry / "EXPERIENCE.md").write_text(f"# Experience: {task}\n\n{m.group(1).strip()}\n")
    idx = _regen_library_index()
    return {"entry": str(entry), "index": str(idx)}


def library_list() -> dict:
    entries = library_entries_dir()
    rows = []
    for d in sorted(entries.iterdir()):
        if d.name.startswith("_") or not d.is_dir():
            continue
        exp = d / "EXPERIENCE.md"
        cue = ""
        if exp.exists():
            for line in exp.read_text(errors="replace").splitlines():
                if line.lower().startswith("cue:"):
                    cue = line.split(":", 1)[1].strip()
                    break
        rows.append(
            {
                "entry": d.name,
                "has_harness": (d / "harness").is_dir(),
                "experience": str(exp) if exp.exists() else None,
                "cue": cue,
            }
        )
    return {"entries": rows, "index": str(entries.parent / "INDEX.md")}


def library_show(task: str) -> dict:
    entry = library_entries_dir() / task_dir(task).name
    if not entry.is_dir():
        raise H2Error(f"no library entry for task {task!r}")
    exp = entry / "EXPERIENCE.md"
    harness = entry / "harness"
    return {
        "entry": str(entry),
        "experience": exp.read_text(errors="replace") if exp.exists() else None,
        "harness": str(harness) if harness.is_dir() else None,
        "harness_files": sorted(p.relative_to(harness).as_posix() for p in harness.rglob("*") if p.is_file())
        if harness.is_dir()
        else [],
        "diff_vs_base": diff_trees(base_tree(), harness) if harness.is_dir() else [],
    }


# ---------------------------------------------------------------------------
# Promotion: carrying a banked round's changes toward the live profile


def live_profile_dir() -> Path:
    """Home of the active profile (where SOUL.md, skills/ and config.yaml live)."""
    try:
        from hermes_constants import get_hermes_home

        return get_hermes_home()
    except Exception:  # noqa: BLE001 - fallback for tests and direct use
        return _hermes_home()


def _classify_file(name: str) -> str:
    if name == "config.yaml":
        return "overlay"
    if name in ("SOUL.md", "hermes.md"):
        return "notes"
    if name.startswith("skills/"):
        return "skill"
    if name.startswith("scripts/"):
        return "scripts"
    return "other"


def _parse_edit_rows(reflection_text: str) -> list[dict]:
    """Parse the reflector's <edits> block into 5-field rows (lenient)."""
    m = re.search(r"<edits>\n(.*?)\n</edits>", reflection_text, re.S)
    if not m:
        return []
    rows: list[dict] = []
    cur: dict | None = None
    for line in m.group(1).splitlines():
        line = line.strip()
        if not line:
            continue
        key, _, val = line.partition(":")
        key = key.strip().lower()
        if key == "component":
            if cur:
                rows.append(cur)
            cur = {"component": val.strip(), "candidates": "", "change": "", "observed": "", "verdict": ""}
        elif cur is not None and key in cur:
            cur[key] = val.strip()
    if cur:
        rows.append(cur)
    return rows


def _rows_for_file(rows: list[dict], name: str) -> list[dict]:
    out = []
    for r in rows:
        c = r["component"]
        if c == name or name.startswith(c + "/") or c.startswith(name + "/"):
            out.append(r)
        elif name == "config.yaml" and c.startswith("config.yaml"):
            out.append(r)
    return out


def promote(task: str) -> dict:
    """Carry-over report for an adopted round.

    Diffs the banked harness against the unmodified base (what this round
    actually changed), attaches the reflector's edit rows and experience, and
    classifies each changed file for the live profile: skills install,
    SOUL.md/hermes.md review (base text is probe scaffolding), config.yaml is
    probe-only and never promoted. Writes runs/<task>/promote.md. This tool
    never writes the live profile; applying changes is the user's step.
    """
    d = task_dir(task)
    entry = library_entries_dir() / task
    if not entry.is_dir():
        raise H2Error(f"no library entry for task {task!r}; adopt the round first")
    meta_p = entry / ".meta.json"
    meta: dict = {}
    if meta_p.exists():
        try:
            meta = json.loads(meta_p.read_text())
        except json.JSONDecodeError:
            meta = {}
    harness = entry / "harness"
    tree = harness if (harness / "SOUL.md").exists() else None
    base = base_tree()
    profile = live_profile_dir()

    changed = diff_tree_files(base, tree) if tree is not None else {}
    reflection = d / "reflection.md"
    rows = _parse_edit_rows(reflection.read_text(errors="replace")) if reflection.exists() else []

    files: list[dict] = []
    for name in sorted(changed):
        st = changed[name]
        kind = _classify_file(name)
        matched = _rows_for_file(rows, name)
        verdicts = sorted({r["verdict"] for r in matched if r["verdict"]})
        if kind == "skill":
            if st == "removed":
                rec = "no action: base probe scaffolding removed from the tree; live profile unaffected"
            else:
                top = name.split("/", 2)
                skill_name = top[1] if len(top) > 1 else name
                rec = f"install: copy '{skill_name}' into the live profile's skills/ (tested under the tree)"
        elif kind == "notes":
            rec = "review: base text is probe scaffolding; carry over only the lesson text you judge transferable"
        elif kind == "overlay":
            rec = "do not promote: probe-only overlay (run budget, approvals mode, secret redaction)"
        elif kind == "scripts":
            rec = "review: probe workspace script; promote as part of a skill only if it is generic"
        else:
            rec = "review"
        files.append({"file": name, "status": st, "kind": kind, "verdict": " / ".join(verdicts), "rec": rec})

    # Report
    md: list[str] = []
    md.append(f"# Promote report: {task}")
    md.append("")
    md.append(f"Generated: {time.strftime('%Y-%m-%d %H:%M %Z')}")
    md.append(f"Adopted: {meta.get('adopted', 'unknown (meta missing)')}")
    md.append(f"Banked tree: {str(tree) if tree else 'none (KEEP_BASE round)'}")
    md.append(f"Base tree: {base}")
    md.append(f"Live profile: {profile}")
    md.append("")
    if not changed:
        md.append("This round kept the base harness. There are no tree changes to carry over;")
        md.append("only the experience below is worth reviewing.")
        md.append("")
    else:
        md.append("## What this round changed (banked tree vs base)")
        for f in files:
            name, st = f["file"], f["status"]
            md.append("")
            md.append(f"### {name} -- {st}")
            if f["verdict"]:
                md.append(f"verdict: {f['verdict']}")
            md.append(f"recommendation: {f['rec']}")
            a = (base / name).read_text(errors="replace") if (base / name).exists() else ""
            b = (tree / name).read_text(errors="replace") if tree and (tree / name).exists() else ""
            if st == "removed":
                diff = _diff_text(a, "", name, "/dev/null")
            elif st == "added":
                diff = _diff_text("", b, "/dev/null", name)
            else:
                diff = _diff_text(a, b, f"base/{name}", f"tree/{name}")
            md.append("```diff")
            md.append(diff.rstrip("\n"))
            md.append("```")
    md.append("")
    md.append("## Evidence")
    md.append("")
    if reflection.exists():
        m = re.search(r"<edits>\n.*?\n</edits>", reflection.read_text(errors="replace"), re.S)
        md.append("Edit rows (reflection.md):")
        md.append("")
        md.append(m.group(0) if m else "(no <edits> block found)")
        md.append("")
    exp = entry / "EXPERIENCE.md"
    if exp.exists():
        md.append("Experience (library entry):")
        md.append("")
        md.append(exp.read_text(errors="replace").strip())
        md.append("")
    md.append("## Carry-over plan (live profile)")
    md.append("")
    md.append("The plugin never writes the live profile. Apply what you approve:")
    md.append("")
    if files:
        for f in files:
            md.append(f"- [ ] {f['file']} -- {f['rec']}" + (f" (verdict: {f['verdict']})" if f["verdict"] else ""))
        cmds = [f for f in files if f["kind"] == "skill" and f["status"] != "removed"]
        if cmds and tree is not None:
            md.append("")
            md.append("Skill install commands:")
            for f in cmds:
                top = f["file"].split("/", 2)
                skill_name = top[1] if len(top) > 1 else top[0]
                md.append(f"  cp -R {tree / 'skills' / skill_name} {profile / 'skills' / skill_name}")
    else:
        md.append("- Nothing to carry over (KEEP_BASE round).")
    md.append("")

    report = d / "promote.md"
    report.write_text("\n".join(md) + "\n")
    install = [
        (f["file"].split("/", 2)[1] if f["file"].count("/") >= 1 else f["file"])
        for f in files
        if f["kind"] == "skill" and f["status"] != "removed"
    ]
    return {
        "task": task,
        "report": str(report),
        "tree": str(tree) if tree else None,
        "adopted": meta.get("adopted"),
        "live_profile": str(profile),
        "files": [
            {"file": f["file"], "status": f["status"], "kind": f["kind"], "verdict": f["verdict"], "recommendation": f["rec"]}
            for f in files
        ],
        "install": sorted(set(install)),
    }


# ---------------------------------------------------------------------------
# Status and garbage collection


def status(task: str) -> dict:
    d = task_dir(task)
    base = {
        "task": task,
        "data_root": str(data_root()),
        "base_tree": str(base_tree()),
        "prompts_dir": str(prompts_dir()),
    }
    if not d.exists():
        return {**base, "exists": False}
    probes = {}
    for p in sorted(d.iterdir()):
        if p.is_dir() and (p / "stdout.log").exists():
            probes[p.name] = {
                "deliverables": _deliverables(p / "ws"),
                "trajectory_bytes": (p / "stdout.log").stat().st_size,
            }
    cdir = candidates_dir()
    candidates = [
        f.name for f in sorted(cdir.iterdir()) if f.is_dir() and f.name.startswith(task + "-")
    ] if cdir.is_dir() else []
    return {
        **base,
        "exists": True,
        "task_dir": str(d),
        "task_md": (d / "task.md").exists(),
        "has_source": (d / "source").is_dir(),
        "probes": probes,
        "candidates": candidates,
        "reflection": (d / "reflection.md").exists(),
        "in_library": (library_entries_dir() / task).is_dir(),
    }


def _recorded_profiles(task: str) -> list[str]:
    """Probe profiles this plugin recorded creating, for the task's probes."""
    d = task_dir(task)
    names: list[str] = []
    if d.is_dir():
        for p in sorted(d.iterdir()):
            if not p.is_dir():
                continue
            name: str | None = None
            meta_p = p / ".meta.json"
            if meta_p.exists():
                try:
                    name = json.loads(meta_p.read_text()).get("profile")
                except (json.JSONDecodeError, OSError):
                    name = None
            if name is None and (p / "stdout.log").exists():
                name = profile_name(task, p.name)
            if name:
                names.append(name)
    return sorted(set(names))


def gc(task: str | None = None, drop_profiles: bool = True, drop_runs: bool = False) -> dict:
    removed_profiles: list[str] = []
    removed_runs: list[str] = []
    if drop_profiles:
        if not task:
            raise H2Error(
                "gc without a task would sweep every harness2-* profile in the root; "
                "pass task=<slug> to delete only the probes this plugin recorded for that task"
            )
        env = {**os.environ, "HERMES_HOME": str(_hermes_home())}
        for name in _recorded_profiles(task):
            if not (_profile_dirs() / name).exists():
                continue
            r = _run_hermes(["profile", "delete", "-y", name], timeout=120, env=env)
            if r.returncode == 0 and not (_profile_dirs() / name).exists():
                removed_profiles.append(name)
    if drop_runs:
        if not task:
            raise H2Error("drop_runs requires a task slug")
        d = task_dir(task)
        if d.exists():
            shutil.rmtree(d)
            removed_runs.append(d.name)
    return {"removed_profiles": removed_profiles, "removed_runs": removed_runs}

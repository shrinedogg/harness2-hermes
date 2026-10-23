#!/usr/bin/env python3
"""Materialize a harness tree as a Hermes probe profile.

Usage:
  python3 scripts/materialize_profile.py <tree> <profile-name> [--home <hermes-home>]

First use: `hermes profile create --clone <name>` (inherits config.yaml,
.env, SOUL.md, skills from the active profile). Every use: overlay the tree
onto the profile so it reflects the tree exactly:
  config.yaml   deep-merged over the active profile's config (the tree
                carries only probe overrides; model wiring inherited)
  .env          re-copied from the active profile
  SOUL.md       replaced by the tree's
  skills/       replaced by the tree's (probe profiles carry no other skills)

The --budget value is written to agent.run_budget_seconds in the merged
config (the gateway CLI rejects a --run-budget flag, so the cap must live in
config).
"""
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("error: PyYAML not available for this interpreter")


def deep_merge(base: dict, overlay: dict) -> dict:
    out = dict(base)
    for k, v in overlay.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("tree")
    ap.add_argument("profile")
    ap.add_argument("--home", default=None)
    ap.add_argument("--budget", type=int, default=None,
                    help="wall-clock run cap in seconds -> agent.run_budget_seconds")
    a = ap.parse_args()

    home = Path(a.home).expanduser() if a.home else \
        Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes")))
    src = Path(a.tree).expanduser().resolve()
    dst = home / "profiles" / a.profile
    if not src.is_dir():
        print(f"error: tree not found: {src}")
        return 1

    if not dst.exists():
        r = subprocess.run(["hermes", "profile", "create", "--clone", a.profile],
                           capture_output=True, text=True)
        if r.returncode != 0 or not dst.exists():
            print(f"error: hermes profile create --clone {a.profile} failed:\n{r.stdout}{r.stderr}")
            return 1

    active_cfg = home / "config.yaml"
    active = {}
    if active_cfg.exists():
        active = yaml.safe_load(active_cfg.read_text()) or {}

    overlay = {}
    overlay_path = src / "config.yaml"
    if overlay_path.exists():
        overlay = yaml.safe_load(overlay_path.read_text()) or {}

    merged = deep_merge(active, overlay)
    if a.budget is not None:
        agent = merged.setdefault("agent", {})
        if not isinstance(agent, dict):
            agent = {}
            merged["agent"] = agent
        agent["run_budget_seconds"] = a.budget
    (dst / "config.yaml").write_text(yaml.safe_dump(merged, sort_keys=False))

    env_src = home / ".env"
    if env_src.exists():
        shutil.copy2(env_src, dst / ".env")

    soul = src / "SOUL.md"
    if soul.exists():
        shutil.copy2(soul, dst / "SOUL.md")

    skills_dst = dst / "skills"
    if skills_dst.exists():
        shutil.rmtree(skills_dst)
    skills_src = src / "skills"
    if skills_src.is_dir():
        shutil.copytree(skills_src, skills_dst)
        skills = sorted(p.name for p in skills_dst.iterdir())
    else:
        skills = []

    print(f"profile materialized: {dst}")
    print(f"  config: {len(merged)} top-level keys (active + overlay)")
    print(f"  skills: {skills}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

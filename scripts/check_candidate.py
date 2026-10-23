#!/usr/bin/env python3
"""Mechanical half of the Harness2 validation gate for a candidate tree.

Checks: config.yaml and SKILL.md frontmatter parse as YAML; skill frontmatter
names match their directory; every skill has a trigger line in SOUL.md or
hermes.md; every script a SKILL.md names exists; context files under 20k
chars. An editor still has to honor the judgment rules (deliverable shape,
evidence) - this gate only catches structural breakage before a rollout.

Usage: python3 scripts/check_candidate.py <candidate-tree>
"""
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("error: PyYAML not available for this interpreter")


def parse_frontmatter(text: str):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return None
    try:
        return yaml.safe_load(m.group(1))
    except yaml.YAMLError:
        return None


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: check_candidate.py <candidate-tree>")
        return 2
    tree = Path(sys.argv[1]).expanduser().resolve()
    if not tree.is_dir():
        print(f"error: not a directory: {tree}")
        return 2

    errors = []

    cfg = tree / "config.yaml"
    if cfg.exists():
        try:
            yaml.safe_load(cfg.read_text())
        except yaml.YAMLError as e:
            errors.append(f"config.yaml: invalid YAML: {e}")

    soul_p, hermes_p = tree / "SOUL.md", tree / "hermes.md"
    always_on = (soul_p.read_text() if soul_p.exists() else "") + "\n" + \
                (hermes_p.read_text() if hermes_p.exists() else "")

    skills_root = tree / "skills"
    if skills_root.is_dir():
        for skill_md in sorted(skills_root.glob("*/SKILL.md")):
            name = skill_md.parent.name
            text = skill_md.read_text()
            fm = parse_frontmatter(text)
            if fm is None:
                errors.append(f"skills/{name}: SKILL.md frontmatter missing or invalid YAML")
                continue
            if fm.get("name") != name:
                errors.append(f"skills/{name}: frontmatter name {fm.get('name')!r} != directory name")
            if not re.search(rf"\b{re.escape(name)}\b", always_on):
                errors.append(f"skills/{name}: no trigger line in SOUL.md or hermes.md")
            for m in re.finditer(r"scripts/([\w.\-]+)", text):
                if not (skills_root / name / "scripts" / m.group(1)).exists():
                    errors.append(f"skills/{name}: names missing script scripts/{m.group(1)}")

    for p in (soul_p, hermes_p):
        if p.exists() and len(p.read_text()) > 20_000:
            errors.append(f"{p.name}: {len(p.read_text())} chars, over the 20k cap")

    if errors:
        print("CANDIDATE INVALID:")
        for e in errors:
            print(f"  - {e}")
        return 1
    print(f"candidate OK: {tree}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Add an adopted harness to the improvement library and regenerate the index.

Usage:
  python3 scripts/library_add.py --task <slug> --adopted <tree-or-KEEP_BASE>
      (--experience <reflection-file> | --no-entry)

Extracts the <experience> block from the reflector's output. Use --no-entry
when the reflector wrote NO_ENTRY.
"""
import argparse
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIB = ROOT / "library"
ENTRIES = LIB / "entries"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True)
    ap.add_argument("--adopted", required=True)
    ap.add_argument("--experience", default=None)
    ap.add_argument("--no-entry", action="store_true")
    ap.add_argument("--cue", default="", help="one-line cue for the index (default: from the block)")
    a = ap.parse_args()

    entry = ENTRIES / a.task
    if entry.exists():
        print(f"error: entry already exists: {entry}")
        return 1
    entry.mkdir(parents=True)

    if a.adopted != "KEEP_BASE":
        tree = (ROOT / a.adopted).resolve()
        if not tree.is_dir():
            print(f"error: adopted tree not found: {tree}")
            return 1
        shutil.copytree(tree, entry / "harness")
        meta = entry / "harness" / ".meta.json"
        if meta.exists():
            meta.unlink()

    if a.no_entry:
        (entry / "EXPERIENCE.md").write_text(f"# Experience: {a.task}\n\nNO_ENTRY\n")
    else:
        if not a.experience or not Path(a.experience).expanduser().exists():
            print("error: --experience file required unless --no-entry")
            return 1
        text = Path(a.experience).expanduser().read_text()
        m = re.search(r"<experience>\n(.*?)\n</experience>", text, re.S)
        if not m:
            print("error: no <experience> block found in reflection file")
            return 1
        body = m.group(1).strip()
        (entry / "EXPERIENCE.md").write_text(f"# Experience: {a.task}\n\n{body}\n")

    # Regenerate the index
    idx = LIB / "INDEX.md"
    rows = [
        "# Improvement library index",
        "",
        "One row per entry. A future Propose/Probe/Compose session reads the index",
        "first and inspects an entry's harness/ and EXPERIENCE.md on demand.",
        "",
    ]
    for d in sorted(ENTRIES.iterdir()):
        if d.name.startswith("_") or not d.is_dir():
            continue
        c = ""
        exp = d / "EXPERIENCE.md"
        if exp.exists():
            for line in exp.read_text().splitlines():
                if line.lower().startswith("cue:"):
                    c = line.split(":", 1)[1].strip()
                    break
        if not c:
            c = "(see EXPERIENCE.md)"
        rows.append(f"- {d.name}/  |  {c}")
    idx.write_text("\n".join(rows) + "\n")

    print(f"library entry added: {entry.relative_to(ROOT)}")
    print(f"index updated: {idx.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

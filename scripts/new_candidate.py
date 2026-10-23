#!/usr/bin/env python3
"""Seed a candidate harness tree from base (or another tree).

Usage:
  python3 scripts/new_candidate.py --task <slug> --id <inv|dom|composed|...>
                                   [--from base] [--note "..."]

Creates candidates/<task>-<id>/ as a full copy of the source tree and writes
.meta.json provenance. After the editor has made its edits, gate with
scripts/check_candidate.py.
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True)
    ap.add_argument("--id", required=True, dest="cid")
    ap.add_argument("--from", dest="src", default="base")
    ap.add_argument("--note", default="")
    a = ap.parse_args()

    src = (ROOT / a.src).resolve()
    dst = (ROOT / "candidates" / f"{a.task}-{a.cid}").resolve()
    if not src.is_dir():
        print(f"error: source tree not found: {src}")
        return 1
    if dst.exists():
        print(f"error: {dst} already exists; delete it first or pick another id")
        return 1
    shutil.copytree(src, dst)
    (dst / ".meta.json").write_text(
        json.dumps({"task": a.task, "id": a.cid, "from": str(src), "note": a.note},
                   indent=2) + "\n"
    )
    print(f"created {dst.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

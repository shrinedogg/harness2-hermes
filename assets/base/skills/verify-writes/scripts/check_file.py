#!/usr/bin/env python3
"""Post-write deliverable checker.

Usage: python3 check_file.py <file>

Prints a short audit: size, line count, placeholder scan, empty-file check.
Exits 1 if defects are found.
"""
import re
import sys

PLACEHOLDERS = re.compile(r"\b(TODO|FIXME|XXX|TBD|PLACEHOLDER|lorem ipsum)\b", re.I)


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: check_file.py <file>")
        return 2
    path = sys.argv[1]
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
    except OSError as e:
        print(f"FAIL: cannot read {path}: {e}")
        return 1

    lines = text.splitlines()
    problems = []
    if not text.strip():
        problems.append("file is empty")
    for i, ln in enumerate(lines):
        if PLACEHOLDERS.search(ln):
            problems.append(f"line {i + 1}: placeholder text: {ln.strip()[:80]}")

    print(f"check_file: {path} bytes={len(text.encode())} lines={len(lines)}")
    if problems:
        print("DEFECTS:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("OK: non-empty, no placeholders")
    return 0


if __name__ == "__main__":
    sys.exit(main())

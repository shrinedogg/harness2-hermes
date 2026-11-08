#!/usr/bin/env python3
"""Regression check for core.py's yaml provider selection.

Run from the repo root in any python (PyYAML-only, ruamel-only, or both):
    python scripts/check_yaml_fallback.py
Prints one machine-readable verdict line and exits 0 on success, 1 on
failure. Keeps the ruamel fallback path honest after core.py edits: the
docker-managed agent venv ships ruamel.yaml, not PyYAML, so the
ModuleNotFoundError fallback is load-bearing there.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main() -> int:
    try:
        import core  # module-level `yaml` provider lives here
    except Exception as e:  # noqa: BLE001
        print(f"verdict=fail reason=core-import {type(e).__name__}: {e}")
        return 1

    try:
        import yaml  # noqa: F401
        provider = "pyyaml"
    except ModuleNotFoundError:
        provider = "ruamel-fallback"

    sample = {
        "b": 2,
        "a": 1,
        "nested": {"z": [1, 2, 3], "y": "text\n"},
        "flag": True,
    }
    ok = True
    dumped = core.yaml.safe_dump(sample, sort_keys=False)
    if core.yaml.safe_load(dumped) != sample:
        ok = False
    try:
        _ = core.yaml.YAMLError
    except AttributeError:
        ok = False
    print(f"verdict={'ok' if ok else 'fail'} provider={provider} roundtrip={'ok' if ok else 'fail'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

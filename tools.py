"""Tool handlers — the code that runs when the model calls a harness2 tool.

Rules: every handler returns a JSON string (success or error), never raises,
and accepts **kwargs for the injected context fields.
"""
from __future__ import annotations

import json

from . import core


def _ok(payload: dict) -> str:
    return json.dumps(payload)


def _err(exc: Exception) -> str:
    return json.dumps({"error": str(exc)})


def _cfg_int(ctx, key: str, default: int) -> int:
    try:
        return int(ctx.get_config(key, default=default) or default)
    except (TypeError, ValueError):
        return default


def _cfg_str(ctx, key: str, default: str) -> str:
    v = ctx.get_config(key, default=default)
    return str(v) if v else default


def make_handlers(ctx):
    """Build handlers with the plugin's settings bound (config is read once at
    register time; changing settings takes effect next session)."""
    budget_default = _cfg_int(ctx, "probe_budget_seconds", 900)
    source_tag = _cfg_str(ctx, "probe_source_tag", "tool")

    def init_task(args: dict, **kwargs) -> str:
        try:
            return _ok(core.init_task(args.get("task", ""), args.get("task_text", ""), args.get("source_dir")))
        except Exception as e:  # noqa: BLE001 - handler must not raise
            return _err(e)

    def probe(args: dict, **kwargs) -> str:
        try:
            budget = args.get("budget") or budget_default
            return _ok(
                core.run_probe(
                    args.get("task", ""),
                    args.get("tree", ""),
                    args.get("probe_id", ""),
                    int(budget),
                    source_tag,
                )
            )
        except Exception as e:
            return _err(e)

    def seed(args: dict, **kwargs) -> str:
        try:
            return _ok(
                core.seed_candidate(
                    args.get("task", ""),
                    args.get("id", ""),
                    args.get("from", "base"),
                    args.get("note", ""),
                )
            )
        except Exception as e:
            return _err(e)

    def check(args: dict, **kwargs) -> str:
        try:
            return _ok(core.check_candidate(args.get("task", ""), args.get("id", "")))
        except Exception as e:
            return _err(e)

    def adopt(args: dict, **kwargs) -> str:
        try:
            return _ok(
                core.adopt(
                    args.get("task", ""),
                    args.get("adopted", ""),
                    args.get("experience_path"),
                    bool(args.get("no_entry", False)),
                )
            )
        except Exception as e:
            return _err(e)

    def library(args: dict, **kwargs) -> str:
        try:
            action = args.get("action", "list")
            if action == "show":
                return _ok(core.library_show(args.get("entry", "")))
            return _ok(core.library_list())
        except Exception as e:
            return _err(e)

    def status(args: dict, **kwargs) -> str:
        try:
            return _ok(core.status(args.get("task", "")))
        except Exception as e:
            return _err(e)

    def gc(args: dict, **kwargs) -> str:
        try:
            return _ok(
                core.gc(
                    args.get("task"),
                    drop_profiles=bool(args.get("drop_profiles", True)),
                    drop_runs=bool(args.get("drop_runs", False)),
                )
            )
        except Exception as e:
            return _err(e)

    return {
        "init": init_task,
        "probe": probe,
        "seed": seed,
        "check": check,
        "adopt": adopt,
        "library": library,
        "status": status,
        "gc": gc,
    }

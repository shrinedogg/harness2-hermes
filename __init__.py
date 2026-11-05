"""harness2 — the Harness^2 self-improvement loop as a Hermes plugin.

Harness^2 (arXiv:2610.14224) refines an agent's execution harness with a
contrastive Propose-Probe-Compose cycle and banks evidence-backed lessons in
an improvement library. This port: the harness is a Hermes profile (config +
SOUL.md + skills), a probe is a fresh one-shot session in an isolated profile,
and the library is durable plugin state.

The deterministic machinery (profile materialization, probe runs, the
structural gate, the library) lives in the tools; the judgment stages
(propose, compose, select, reflect) run in the host agent's own session under
the bundled skills, which point at the verbatim stage prompts shipped in
assets/prompts/.
"""
from __future__ import annotations

import logging
from pathlib import Path

from . import schemas, tools

logger = logging.getLogger(__name__)

_PLUGIN_DIR = Path(__file__).resolve().parent
_TOOLSET = "harness2"


def register(ctx) -> None:
    """Wire schemas to handlers and register the bundled stage skills."""
    h = tools.make_handlers(ctx)

    ctx.register_tool(name="harness2_init", toolset=_TOOLSET, schema=schemas.INIT, handler=h["init"])
    ctx.register_tool(name="harness2_probe", toolset=_TOOLSET, schema=schemas.PROBE, handler=h["probe"])
    ctx.register_tool(name="harness2_seed", toolset=_TOOLSET, schema=schemas.SEED, handler=h["seed"])
    ctx.register_tool(name="harness2_check", toolset=_TOOLSET, schema=schemas.CHECK, handler=h["check"])
    ctx.register_tool(name="harness2_adopt", toolset=_TOOLSET, schema=schemas.ADOPT, handler=h["adopt"])
    ctx.register_tool(name="harness2_promote", toolset=_TOOLSET, schema=schemas.PROMOTE, handler=h["promote"])
    ctx.register_tool(name="harness2_library", toolset=_TOOLSET, schema=schemas.LIBRARY, handler=h["library"])
    ctx.register_tool(name="harness2_status", toolset=_TOOLSET, schema=schemas.STATUS, handler=h["status"])
    ctx.register_tool(name="harness2_gc", toolset=_TOOLSET, schema=schemas.GC, handler=h["gc"])

    skills_dir = _PLUGIN_DIR / "skills"
    if skills_dir.is_dir():
        for child in sorted(skills_dir.iterdir()):
            skill_md = child / "SKILL.md"
            if child.is_dir() and skill_md.exists():
                ctx.register_skill(child.name, skill_md)

#!/usr/bin/env bash
# Cron monitor for the harness2-hermes post-update smoke test.
#
# Emits exactly one deterministic line: the current hermes version and the
# version of the last green smoke run. The cron scheduler runs this every
# tick with no LLM; the agent job only wakes when this output CHANGES, which
# happens when a new version appears (tested=old) and once more after a green
# run (tested=new). Stable state = identical output = zero agent runs.
REPO="$(cd "$(dirname "$0")/.." && pwd)"
VER="$(hermes --version 2>/dev/null | head -1)" || VER="hermes CLI missing"
TESTED="$(cat "$REPO/runs/.last-green-version" 2>/dev/null)" || TESTED="none"
echo "$VER | tested=$TESTED"

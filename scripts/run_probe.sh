#!/usr/bin/env bash
# Run one probe: materialize a candidate harness tree as a Hermes profile,
# execute the task in a fresh workspace and session, capture the trajectory
# (stream-json) and deliverables.
#
# Usage:
#   bash scripts/run_probe.sh <tree> <profile-name> <task-dir> [run-budget-sec]
#     <tree>           base | candidates/<task>-<id>   (repo-relative or absolute)
#     <profile-name>   e.g. harness2-base, harness2-<task>-inv
#     <task-dir>       runs/<task>  (must contain task.md, optional source/)
#     [run-budget-sec] wall-clock ceiling for the run (default 900)
#
# Writes under <task-dir>/<profile-name>/:
#   ws/             probe workspace (.hermes.md, scripts/, out/ deliverables)
#   stdout.log      stream-json trajectory (the probe's transcript)
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
TREE="${1:?usage: run_probe.sh <tree> <profile-name> <task-dir> [budget-sec]}"
PROFILE="${2:?profile name required}"
TASK_DIR="${3:?task dir required, e.g. runs/<task>}"
BUDGET="${4:-900}"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"

TASK_DIR="$(cd "$TASK_DIR" && pwd)"
TREE="$(cd "$REPO" && cd "$TREE" && pwd)"
PROBE_DIR="$TASK_DIR/$PROFILE"
WS="$PROBE_DIR/ws"
mkdir -p "$WS/out"

# 1. Materialize the profile (create on first use, refresh on re-use)
python3 "$REPO/scripts/materialize_profile.py" "$TREE" "$PROFILE" \
  --home "$HERMES_HOME" --budget "$BUDGET"

# 2. Build the workspace
cp "$TASK_DIR/task.md" "$WS/task.md"
if [ -d "$TASK_DIR/source" ]; then cp -R "$TASK_DIR/source" "$WS/source"; fi
if [ -f "$TREE/hermes.md" ]; then cp "$TREE/hermes.md" "$WS/.hermes.md"; fi
if [ -d "$TREE/scripts" ]; then cp -R "$TREE/scripts" "$WS/scripts"; fi
if [ -d "$TREE/skills" ]; then
  for d in "$TREE"/skills/*/scripts; do
    [ -d "$d" ] || continue
    mkdir -p "$WS/scripts"
    cp "$d"/*.py "$WS/scripts/" 2>/dev/null || true
  done
fi

# 3. Run the task: fresh one-shot session, pinned workspace, tagged, budgeted
hermes -p "$PROFILE" chat \
  --in "$WS" \
  --query-file "$WS/task.md" \
  --format stream-json \
  --source tool \
  > "$PROBE_DIR/stdout.log" 2>&1 || {
  echo "probe run failed; see $PROBE_DIR/stdout.log" >&2
  exit 1
}

# 4. Best effort: also copy any session jsonl the profile produced
PROF_SESSIONS="$HERMES_HOME/profiles/$PROFILE/sessions"
NEWEST="$(ls -t "$PROF_SESSIONS"/*.jsonl 2>/dev/null | head -1 || true)"
if [ -n "$NEWEST" ]; then cp "$NEWEST" "$PROBE_DIR/transcript.jsonl"; fi

DELIVERABLES="$(ls -A "$WS/out" 2>/dev/null | wc -l | tr -d ' ')"
echo "probe complete: $PROBE_DIR"
echo "  trajectory:   $PROBE_DIR/stdout.log (stream-json)"
echo "  deliverables: $DELIVERABLES file(s) in $WS/out"

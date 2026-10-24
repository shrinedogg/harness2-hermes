#!/usr/bin/env bash
# Post-update smoke test for the harness2-hermes scaffold.
#
# Runs the base-harness (H0) probe if the hermes version differs from the
# last green run, verifies the deliverable, logs to runs/update-log.md, and
# updates runs/.last-green-version on success.
#
# Usage: bash scripts/smoke.sh
# Exit:  0 = green, or nothing to do (version unchanged since last green)
#        1 = probe failed (diagnosis in runs/update-log.md + stdout.log)
set -uo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
MARKER="$REPO/runs/.last-green-version"
LOG="$REPO/runs/update-log.md"
PROFILE="harness2-smoke-ref"
RUN_DIR="$REPO/runs/smoke-test/$PROFILE"
TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

VER="$(hermes --version 2>/dev/null | head -1)" || VER="hermes CLI missing"

if [ -f "$MARKER" ] && [ "$(cat "$MARKER")" = "$VER" ]; then
  echo "smoke: no version change since last green run ($VER); nothing to do"
  exit 0
fi

echo "smoke: version change detected; running base-harness probe"
bash "$REPO/scripts/run_probe.sh" base "$PROFILE" "$REPO/runs/smoke-test" 300
RC=$?
if [ $RC -ne 0 ]; then
  echo "- $TS FAIL $VER (run_probe exit $RC)" >> "$LOG"
  echo "smoke: FAIL $VER (probe command failed; see $RUN_DIR/stdout.log)"
  exit 1
fi

ANSWER="$(cat "$RUN_DIR/ws/out/answer.txt" 2>/dev/null)"
if [ "$ANSWER" = "OK" ]; then
  hermes profile delete -y "$PROFILE" >/dev/null 2>&1 || true
  echo "$VER" > "$MARKER"
  echo "- $TS GREEN $VER" >> "$LOG"
  echo "smoke: GREEN $VER"
  exit 0
else
  hermes profile delete -y "$PROFILE" >/dev/null 2>&1 || true
  echo "- $TS FAIL $VER (deliverable='${ANSWER:-missing}')" >> "$LOG"
  echo "smoke: FAIL $VER (deliverable wrong: '${ANSWER:-missing}'; see $RUN_DIR/stdout.log)"
  exit 1
fi

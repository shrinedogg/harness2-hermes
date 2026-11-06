#!/usr/bin/env bash
# Cron monitor for the harness2 post-update smoke job.
#
# cron/monitor.py (hermes source) hashes the EXACT output bytes -- no
# normalization -- and wakes the job when the hash changes; a source
# failure is an error, never a change. The output must therefore be
# byte-stable between ticks and change exactly when (a) the hermes
# version or (b) the harness2 plugin code changes:
#
#   hermes:      first line of `hermes --version` (the job's wake
#                condition), or the plugin's version when the CLI is
#                unavailable in the cron env
#   plugin:      version from the live plugin's plugin.yaml
#   fingerprint: sha256 over a pinned file set of the live plugin
#
# No timestamps, no locale or whitespace drift, deterministic file
# order. Set HARNESS2_PLUGIN_DIR to fingerprint a copy (tests).
set -euo pipefail

PLUGIN_DIR="${HARNESS2_PLUGIN_DIR:-$HOME/.hermes/plugins/harness2}"

# File set to fingerprint: pinned and sorted, so runtime dirs in the
# live plugin (__pycache__, runs, ...) never affect the hash.
PINNED_FILES="core.py plugin.yaml"

if command -v sha256sum >/dev/null 2>&1; then
  sha256_file() { sha256sum "$1" | awk '{print $1}'; }
  sha256_stdin() { sha256sum | awk '{print $1}'; }
else
  sha256_file() { shasum -a 256 "$1" | awk '{print $1}'; }
  sha256_stdin() { shasum -a 256 | awk '{print $1}'; }
fi
if ! command -v sha256sum >/dev/null 2>&1 && ! command -v shasum >/dev/null 2>&1; then
  echo "error: no sha256sum or shasum on PATH" >&2
  exit 1
fi

# Version pinned in the live plugin's plugin.yaml; empty when absent.
plugin_version() {
  if [ -f "$PLUGIN_DIR/plugin.yaml" ]; then
    sed -n 's/^version:[[:space:]]*//p' "$PLUGIN_DIR/plugin.yaml"
  fi
}

# sha256 over the pinned file set of the live plugin. A missing file
# hashes as "<name>:missing", so the fingerprint changes instead of
# failing.
fingerprint() {
  local f lines=""
  for f in $PINNED_FILES; do
    if [ -f "$PLUGIN_DIR/$f" ]; then
      lines+="$f:$(sha256_file "$PLUGIN_DIR/$f")"$'\n'
    else
      lines+="$f:missing"$'\n'
    fi
  done
  printf '%s' "$lines" | sha256_stdin
}

pv="$(plugin_version)"
[ -n "$pv" ] || pv="unknown"

# 1. hermes version: the job's wake condition. First line only, so the
# trailing update-check lines of `hermes --version` can never drift.
# The full output is captured before truncation: no `head` in the pipe,
# which would SIGPIPE the CLI and fail the pipeline under pipefail.
hermes_line=""
if hv_full="$(hermes --version 2>/dev/null)" && [ -n "$hv_full" ]; then
  hermes_line="${hv_full%%$'\n'*}"
fi
[ -n "$hermes_line" ] || hermes_line="CLI unavailable (plugin $pv)"

# 2. live plugin state.
printf 'hermes: %s\n' "$hermes_line"
printf 'plugin: %s\n' "$pv"
printf 'fingerprint: %s\n' "$(fingerprint)"

#!/usr/bin/env bash
# Cron entry point for the nightly "dream" consolidation pass. Self-locates the
# tool, sets a sane PATH (cron has a minimal one), single-instances via a lock,
# and logs to the memories repo. Never fails loudly — it's unattended.
set -uo pipefail
TOOL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MEM_HOME="${MEM_HOME:-$HOME/workplace/mymemories}"

# cron runs with a bare PATH; make sure `claude`, `git`, `python3` resolve.
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

LOG_DIR="$MEM_HOME/.dream-logs"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/$(date +%Y-%m-%d).log"
LOCK="$LOG_DIR/.lock"

# Single-instance: skip if a run is already in flight.
if command -v flock >/dev/null 2>&1; then
  exec 9>"$LOCK" || exit 0
  flock -n 9 || { echo "$(date) another dream run in flight; skip" >>"$LOG"; exit 0; }
fi

{
  echo "===== dream run $(date) ====="
  python3 "$TOOL_DIR/dream.py" "$@"
  echo "===== end $(date) ====="
} >>"$LOG" 2>&1

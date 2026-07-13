#!/usr/bin/env bash
# SessionStart hook. Two jobs, both cheap and best-effort:
#   1. Symlink the current project's memory dir into the central repo (autolink).
#   2. Sync the central repo DOWN (git pull --ff-only), in the background.
# Reads the hook JSON on stdin ("cwd"). Never blocks the session; never fails it.
set -uo pipefail
TOOL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MEM_HOME="${MEM_HOME:-$HOME/workplace/mymemories}"

payload="$(cat)"
cwd="$(printf '%s' "$payload" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("cwd",""))' 2>/dev/null)"
[ -z "$cwd" ] && cwd="$PWD"

# 1. Symlink this project (local, fast).
[ -x "$TOOL_DIR/autolink.sh" ] && "$TOOL_DIR/autolink.sh" "$cwd" >/dev/null 2>&1 || true

# 2. Pull central memories down (background, timed out, detached — never hangs
#    the session or leaks a long-lived process onto it).
if [ -d "$MEM_HOME/.git" ]; then
  ( timeout 20 git -C "$MEM_HOME" pull --ff-only ) >/dev/null 2>&1 &
  disown 2>/dev/null || true
fi
exit 0

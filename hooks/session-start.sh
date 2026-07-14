#!/usr/bin/env bash
# Claude Code SessionStart hook. Best-effort, never blocks or fails the session:
#   1. Link this project's memory partition into the central repo (via mymem).
#   2. Pull the central repo down (git pull --ff-only), backgrounded.
# The repo (memcore + mymem) IS the plugin root.
set -uo pipefail
REPO_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
MEM_HOME="${MEM_HOME:-$HOME/workplace/mymemories}"

payload="$(cat)"
cwd="$(printf '%s' "$payload" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("cwd",""))' 2>/dev/null)"
[ -z "$cwd" ] && cwd="$PWD"

# 1. Link this project (local, fast). Only if it already has a partition.
MEM_HOME="$MEM_HOME" python3 "$REPO_ROOT/mymem" --provider claude link --project "$cwd" >/dev/null 2>&1 || true

# 2. Pull central memories (background, timed out, detached).
if [ -d "$MEM_HOME/.git" ]; then
  ( timeout 20 git -C "$MEM_HOME" pull --ff-only ) >/dev/null 2>&1 &
  disown 2>/dev/null || true
fi
exit 0

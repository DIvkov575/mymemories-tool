#!/usr/bin/env bash
# Codex SessionStart hook (best-effort): pull the central memories repo so this
# session sees the latest. Never blocks or fails the session.
set -uo pipefail
MEM_HOME="${MEM_HOME:-$HOME/workplace/mymemories}"
if [ -d "$MEM_HOME/.git" ]; then
  ( timeout 20 git -C "$MEM_HOME" pull --ff-only ) >/dev/null 2>&1 &
  disown 2>/dev/null || true
fi
exit 0

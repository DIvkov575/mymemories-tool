#!/usr/bin/env bash
# SessionStart hook: ensure the current project is symlinked into the private
# memories repo. Reads the hook JSON on stdin (common field "cwd"). Silent
# unless it acts. autolink.sh lives next to this hook (the tool repo); it
# resolves the private memories location itself via MEM_HOME.
set -uo pipefail
TOOL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
payload="$(cat)"
cwd="$(printf '%s' "$payload" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("cwd",""))' 2>/dev/null)"
[ -z "$cwd" ] && cwd="$PWD"
[ -x "$TOOL_DIR/autolink.sh" ] && "$TOOL_DIR/autolink.sh" "$cwd" >/dev/null 2>&1 || true
exit 0

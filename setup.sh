#!/usr/bin/env bash
# One-time setup: create the tool-local venv and install embedding deps.
# The venv lives next to this tool (not in the private memories repo).
# Safe to re-run.
set -uo pipefail
TOOL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 -m venv "$TOOL_DIR/.venv"
"$TOOL_DIR/.venv/bin/python3" -m pip install --upgrade pip
"$TOOL_DIR/.venv/bin/python3" -m pip install -r "$TOOL_DIR/requirements.txt"
echo "setup complete: $TOOL_DIR/.venv"

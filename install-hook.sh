#!/usr/bin/env bash
# Register the SessionStart hook that auto-symlinks projects on session start,
# and install the /memorize + /recall slash-commands into ~/.claude/commands/.
# Idempotent: merges into ~/.claude/settings.json without clobbering other keys,
# and is a no-op if the hook is already present. Run once per device.
#
#   ./install-hook.sh
#   CLAUDE_HOME=... ./install-hook.sh   # override ~/.claude location
set -uo pipefail

TOOL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_HOME="${CLAUDE_HOME:-$HOME/.claude}"
SETTINGS="$CLAUDE_HOME/settings.json"
HOOK_CMD="$TOOL_DIR/hooks/session-start.sh"

[ -x "$HOOK_CMD" ] || chmod +x "$HOOK_CMD" 2>/dev/null || true

# Install slash-commands (copy, not symlink — Claude Code reads them directly).
CMD_DIR="$CLAUDE_HOME/commands"
mkdir -p "$CMD_DIR"
for c in memorize recall; do
  if [ -f "$TOOL_DIR/commands/$c.md" ]; then
    cp "$TOOL_DIR/commands/$c.md" "$CMD_DIR/$c.md"
    echo "installed /$c command"
  fi
done

python3 - "$SETTINGS" "$HOOK_CMD" <<'PY'
import json, os, sys
settings_path, hook_cmd = sys.argv[1], sys.argv[2]

os.makedirs(os.path.dirname(settings_path), exist_ok=True)
try:
    with open(settings_path) as f:
        cfg = json.load(f)
except (FileNotFoundError, ValueError):
    cfg = {}

hooks = cfg.setdefault("hooks", {})
groups = hooks.setdefault("SessionStart", [])

# Already registered? (match by command substring, any matcher)
already = any(
    h.get("command") == hook_cmd
    for g in groups for h in g.get("hooks", [])
)
if already:
    print("hook already registered; no change")
else:
    groups.append({
        "matcher": "startup",
        "hooks": [{"type": "command", "command": hook_cmd}],
    })
    with open(settings_path, "w") as f:
        json.dump(cfg, f, indent=2)
    print(f"registered SessionStart hook -> {hook_cmd}")
PY

python3 -m json.tool "$SETTINGS" >/dev/null && echo "settings.json valid"

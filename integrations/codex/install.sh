#!/usr/bin/env bash
# Install the mymemories Codex integration:
#   1. Copy the memory-consolidation + memorize skills into ~/.codex/skills/
#   2. Link every manifest partition into its project's AGENTS.md (mymem install)
# Idempotent. Run once per device (after cloning the memories repo to $MEM_HOME).
#
#   ./install.sh
#   CODEX_HOME=... MEM_HOME=... ./install.sh
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$HERE/../.." && pwd)"        # integrations/codex -> repo root
CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"

# 1. Skills
for s in memory-consolidation memorize; do
  dst="$CODEX_HOME/skills/$s"
  mkdir -p "$dst"
  cp "$HERE/skills/$s/SKILL.md" "$dst/SKILL.md"
  echo "installed skill -> $dst"
done

# 2. Point each partition at its project's AGENTS.md
python3 "$REPO_ROOT/mymem" --provider codex install
echo "Codex integration installed. Consolidate with:"
echo "  python3 \"$REPO_ROOT/mymem\" --provider codex dream --partition <name> --dry-run"

# Note: Codex auto-pull on session start is delivered via the AGENTS.md reminder
# (Codex reliably reads AGENTS.md at start). hooks/hooks.json is a belt-and-
# suspenders SessionStart pull for when mymemories is installed as a full Codex
# plugin (registered via plugin.json's "hooks" field).
echo "auto-pull reminder written into each linked project's AGENTS.md"

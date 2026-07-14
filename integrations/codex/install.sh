#!/usr/bin/env bash
# Install the mymemories Codex integration:
#   1. Copy the memory-consolidation skill into ~/.codex/skills/
#   2. Link every manifest partition into its project's AGENTS.md (mymem install)
# Idempotent. Run once per device (after cloning the memories repo to $MEM_HOME).
#
#   ./install.sh
#   CODEX_HOME=... MEM_HOME=... ./install.sh
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$HERE/../.." && pwd)"        # integrations/codex -> repo root
CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"

# 1. Skill
SKILL_DST="$CODEX_HOME/skills/memory-consolidation"
mkdir -p "$SKILL_DST"
cp "$HERE/skills/memory-consolidation/SKILL.md" "$SKILL_DST/SKILL.md"
echo "installed skill -> $SKILL_DST"

# 2. Point each partition at its project's AGENTS.md
python3 "$REPO_ROOT/mymem" --provider codex install
echo "Codex integration installed. Consolidate with:"
echo "  python3 \"$REPO_ROOT/mymem\" --provider codex dream --partition <name> --dry-run"

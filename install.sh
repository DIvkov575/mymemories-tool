#!/usr/bin/env bash
# Top-level installer. Links every manifest partition into whichever coding
# agent(s) are present, using mymem's provider auto-detection. Also installs
# each provider's integration (Claude plugin commands/hook are loaded by the
# plugin system; Codex skill is copied by its own install.sh).
#
#   ./install.sh                 # auto-detect and link for all available providers
#   MYMEM_PROVIDER=codex ./install.sh
set -uo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Detected providers:"
python3 "$REPO/mymem" providers

for prov in claude codex; do
  if python3 "$REPO/mymem" providers | grep -q "^$prov *available"; then
    echo "== linking partitions for $prov =="
    python3 "$REPO/mymem" --provider "$prov" install || true
  fi
done
echo "Done. Consolidate with: python3 $REPO/mymem dream --dry-run"

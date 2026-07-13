#!/usr/bin/env bash
# Install (or remove) the nightly "dream" consolidation cron job.
# Idempotent: rewrites only our own crontab line, identified by a tag comment.
#
#   ./install-dream.sh            # install nightly job (default 03:30)
#   DREAM_HOUR=4 DREAM_MIN=15 ./install-dream.sh
#   ./install-dream.sh --remove   # uninstall
set -uo pipefail
TOOL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CRON_CMD="$TOOL_DIR/hooks/dream-cron.sh"
TAG="# mymemories-dream"
HOUR="${DREAM_HOUR:-3}"
MIN="${DREAM_MIN:-30}"

chmod +x "$CRON_CMD" "$TOOL_DIR/dream.py" 2>/dev/null || true

current="$(crontab -l 2>/dev/null || true)"
# Strip any existing dream line (and its tag) so we can re-add cleanly.
filtered="$(printf '%s\n' "$current" | grep -vF "$TAG" || true)"

if [ "${1:-}" = "--remove" ]; then
  printf '%s\n' "$filtered" | crontab -
  echo "removed dream cron job"
  exit 0
fi

line="$MIN $HOUR * * * $CRON_CMD $TAG"
{ printf '%s\n' "$filtered"; printf '%s\n' "$line"; } | sed '/^$/d' | crontab -
echo "installed dream cron job: $MIN $HOUR daily"
echo "  -> $CRON_CMD"
crontab -l 2>/dev/null | grep -F "$TAG"

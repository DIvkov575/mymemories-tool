#!/usr/bin/env bash
# Install: symlink each memory partition (in the PRIVATE memories repo) into the
# Claude Code location the harness auto-loads from, so a partition is loaded
# ONLY when its project is open — while all partitions live centrally in the
# private repo under git.
#
# This is the PUBLIC tool; your memories live separately in $MEM_HOME.
# Idempotent. Safe to re-run after `git pull` on any device.
#
#   ./install.sh                   # install all partitions from the manifest
#   MEM_HOME=/path ./install.sh    # override private memories location
#   CLAUDE_HOME=... ./install.sh   # override ~/.claude location
set -euo pipefail

HOME_DIR="${HOME:?HOME must be set}"
MEM_HOME="${MEM_HOME:-$HOME_DIR/workplace/mymemories}"   # private memories repo
CLAUDE_PROJECTS="${CLAUDE_HOME:-$HOME_DIR/.claude}/projects"
MANIFEST="$MEM_HOME/manifest.tsv"

# Mangle an absolute path the way Claude Code names its projects/ dirs:
# every character that is not a letter or digit becomes '-'.
mangle() { printf '%s' "$1" | sed 's/[^A-Za-z0-9]/-/g'; }

[ -d "$MEM_HOME" ] || { echo "memories repo not found at $MEM_HOME (set MEM_HOME)" >&2; exit 1; }
[ -f "$MANIFEST" ] || { echo "no manifest at $MANIFEST" >&2; exit 1; }

while IFS=$'\t' read -r partition relpath; do
  case "$partition" in ''|\#*) continue ;; esac          # skip blanks/comments
  [ -d "$MEM_HOME/$partition" ] || { echo "SKIP $partition (no dir in memories repo)"; continue; }

  abs="$HOME_DIR/$relpath"
  link="$CLAUDE_PROJECTS/$(mangle "$abs")/memory"
  mkdir -p "$(dirname "$link")"

  if [ -L "$link" ]; then
    rm "$link"                                            # replace stale symlink
  elif [ -e "$link" ]; then
    # A real dir is already there (pre-existing memories). Fold any non-cozempic
    # files into the partition, back up, then replace with the symlink.
    for f in "$link"/*.md; do
      [ -e "$f" ] || continue
      b="$(basename "$f")"; [ "$b" = "cozempic_digest.md" ] && continue
      [ -e "$MEM_HOME/$partition/$b" ] || cp "$f" "$MEM_HOME/$partition/$b"
    done
    mv "$link" "$link.pre-mymemories.bak"
    echo "  (backed up existing dir -> $(basename "$link").pre-mymemories.bak)"
  fi

  ln -s "$MEM_HOME/$partition" "$link"
  echo "LINK $partition -> $link"
done < "$MANIFEST"

echo "Done. Partitions are symlinked; edit/commit them centrally in $MEM_HOME."

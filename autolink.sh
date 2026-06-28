#!/usr/bin/env bash
# Ensure the given project dir (default: $PWD) is partitioned + symlinked into
# the PRIVATE memories repo ($MEM_HOME). Idempotent. Creates a partition ONLY if
# the project's real memory dir already has non-plugin memories, OR the partition
# already exists. Never writes memory content.
#
#   autolink.sh [project-abs-path]
#   MEM_HOME=/path autolink.sh ...
set -uo pipefail
PROJ="${1:-$PWD}"
HOME_DIR="${HOME:?}"
MEM_HOME="${MEM_HOME:-$HOME_DIR/workplace/mymemories}"
mangle() { printf '%s' "$1" | sed 's/[^A-Za-z0-9]/-/g'; }

link="$HOME_DIR/.claude/projects/$(mangle "$PROJ")/memory"

# Already a symlink into the repo? Nothing to do.
if [ -L "$link" ]; then exit 0; fi

# Derive a partition name: path relative to $HOME, lowercased, slashes->dashes.
rel="${PROJ#$HOME_DIR/}"
partition="$(printf '%s' "$rel" | tr 'A-Z/' 'a-z-')"

has_real_mem=0
if [ -d "$link" ]; then
  for f in "$link"/*.md; do
    [ -e "$f" ] || continue
    b="$(basename "$f")"; [ "$b" = cozempic_digest.md ] && continue
    has_real_mem=1; break
  done
fi

# Act only if memories exist already, or the repo partition already exists.
if [ "$has_real_mem" -eq 0 ] && [ ! -d "$MEM_HOME/$partition" ]; then exit 0; fi

mkdir -p "$MEM_HOME/$partition"
# Fold any existing non-plugin memories into the partition, then back up.
if [ -d "$link" ] && [ ! -L "$link" ]; then
  for f in "$link"/*.md; do
    [ -e "$f" ] || continue
    b="$(basename "$f")"; [ "$b" = cozempic_digest.md ] && continue
    [ -e "$MEM_HOME/$partition/$b" ] || cp "$f" "$MEM_HOME/$partition/$b"
  done
  mv "$link" "$link.pre-mymemories.bak"
fi
mkdir -p "$(dirname "$link")"
ln -s "$MEM_HOME/$partition" "$link"

# Register in manifest if absent (path relative to $HOME).
if ! grep -q "^$partition	" "$MEM_HOME/manifest.tsv" 2>/dev/null; then
  printf '%s\t%s\n' "$partition" "$rel" >> "$MEM_HOME/manifest.tsv"
fi
echo "autolink: $partition -> $link" >&2

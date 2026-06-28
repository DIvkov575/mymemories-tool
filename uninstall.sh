#!/usr/bin/env bash
# Uninstall: remove the symlinks created by install.sh and restore a plain
# real memory dir (copied out of the private repo) at each project location, so
# Claude Code keeps working with local-only memories. The repos are untouched.
#
#   ./uninstall.sh
#   MEM_HOME=/path ./uninstall.sh
set -euo pipefail

HOME_DIR="${HOME:?HOME must be set}"
MEM_HOME="${MEM_HOME:-$HOME_DIR/workplace/mymemories}"   # private memories repo
CLAUDE_PROJECTS="${CLAUDE_HOME:-$HOME_DIR/.claude}/projects"
MANIFEST="$MEM_HOME/manifest.tsv"

mangle() { printf '%s' "$1" | sed 's/[^A-Za-z0-9]/-/g'; }

[ -f "$MANIFEST" ] || { echo "no manifest at $MANIFEST (set MEM_HOME)" >&2; exit 1; }

while IFS=$'\t' read -r partition relpath; do
  case "$partition" in ''|\#*) continue ;; esac
  link="$CLAUDE_PROJECTS/$(mangle "$HOME_DIR/$relpath")/memory"
  if [ -L "$link" ]; then
    rm "$link"
    cp -R "$MEM_HOME/$partition" "$link"        # leave a real, local copy behind
    [ -e "$link/.git" ] && rm "$link/.git"      # drop any stray git pointer
    echo "RESTORED $partition -> $link (now a plain dir)"
  else
    echo "SKIP $partition (not a symlink)"
  fi
done < "$MANIFEST"

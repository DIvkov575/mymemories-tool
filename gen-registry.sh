#!/usr/bin/env bash
# Regenerate REGISTRY.md (the cross-partition awareness file) and ensure every
# partition's MEMORY.md carries the awareness header pointing back to it.
# Operates on the PRIVATE memories repo ($MEM_HOME). Run after adding/removing
# partitions or memories.
set -euo pipefail
HOME_DIR="${HOME:?HOME must be set}"
MEM_HOME="${MEM_HOME:-$HOME_DIR/workplace/mymemories}"
REG="$MEM_HOME/REGISTRY.md"
HDR_MARK="<!-- mymemories-awareness -->"

[ -d "$MEM_HOME" ] || { echo "memories repo not found at $MEM_HOME (set MEM_HOME)" >&2; exit 1; }

# Partition dirs to skip when building the registry (tool/docs artifacts that may
# coexist if someone points MEM_HOME at a combined layout).
skip_partition() {
  case "$1" in docs|commands|hooks|.git|.venv) return 0 ;; *) return 1 ;; esac
}

{
  echo "$HDR_MARK"
  echo "# Memory partition registry"
  echo
  echo "Memories are **partitioned per project** and live centrally in this git repo."
  echo "Only the current project's partition auto-loads. **Other partitions are NOT"
  echo "loaded but ARE readable on demand** — Read or grep \`<repo>/<partition>/\` when a"
  echo "task touches another project. Partitions:"
  echo
  for d in "$MEM_HOME"/*/; do
    p="$(basename "$d")"
    skip_partition "$p" && continue
    [ -f "$d/MEMORY.md" ] || continue
    n=$(find "$d" -name '*.md' -not -name 'MEMORY.md' -not -name 'cozempic_digest.md' | wc -l | tr -d ' ')
    echo "- **$p** ($n memories) — see \`$p/MEMORY.md\`"
  done
} > "$REG"
echo "wrote $REG"

# Prepend awareness header to each MEMORY.md (idempotent: skip if already present).
for m in "$MEM_HOME"/*/MEMORY.md; do
  [ -e "$m" ] || continue
  grep -q "$HDR_MARK" "$m" 2>/dev/null && continue
  tmp="$m.tmp"
  {
    echo "$HDR_MARK"
    echo "<!-- This is one partition of a central memory repo. Other projects'"
    echo "     memories are listed in REGISTRY.md and are readable on demand. -->"
    echo
    cat "$m"
  } > "$tmp" && mv "$tmp" "$m"
  echo "header added: ${m#$MEM_HOME/}"
done

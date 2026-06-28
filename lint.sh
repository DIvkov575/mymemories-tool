#!/usr/bin/env bash
# Resolve [[wiki-links]] across all partitions and report problems.
# This is the resolution layer the harness does NOT provide: it builds a
# slug -> file map from frontmatter `name:` fields and checks every [[link]].
# Plain POSIX shell + grep/sed for portability (macOS bash 3.2, Linux).
#
#   ./lint.sh        # report dangling links + orphans; exit 1 if any dangling
# No `set -e`: this is a report; many greps legitimately exit nonzero (no match).
set -uo pipefail
HOME_DIR="${HOME:?HOME must be set}"
MEM_HOME="${MEM_HOME:-$HOME_DIR/workplace/mymemories}"   # private memories repo

# Only the per-project memory partitions are linted. Any prose docs that might
# coexist (README.md, format.md, docs/) legitimately contain literal [[link]]
# syntax examples and are not memory content, so they are excluded.
mem_files() {
  find "$MEM_HOME" -name '*.md' \
    -not -path '*/.git/*' \
    -not -path '*/.venv/*' \
    -not -path "$MEM_HOME/docs/*" \
    -not -name 'REGISTRY.md' \
    -not -name 'README.md' \
    -not -name 'format.md' \
    -not -name 'museum-software-ideas.md'
}
fact_files() { mem_files | grep -v '/MEMORY\.md$'; }

# 1. Known slugs: first `name:` line of each fact file.
SLUGS="$(while IFS= read -r f; do
  grep -m1 '^name:' "$f" 2>/dev/null | sed 's/^name: *//; s/\r//'
done < <(fact_files) | sort -u)"
echo "== Known slugs: $(printf '%s\n' "$SLUGS" | grep -c . ) =="

# 2. Referenced slugs: every [[link]] across all files (strip |alias and type:).
REFS="$(mem_files | while IFS= read -r f; do
  grep -oE '\[\[[^]]+\]\]' "$f" 2>/dev/null
done | sed 's/^\[\[//; s/\]\]$//; s/|.*//; s/.*://' | sort -u)"

# 3. Dangling: referenced but not a known slug.
dangling=0
while IFS= read -r r; do
  [ -z "$r" ] && continue
  if ! printf '%s\n' "$SLUGS" | grep -qxF "$r"; then
    echo "DANGLING [[$r]]"
    dangling=$((dangling+1))
  fi
done < <(printf '%s\n' "$REFS")

# 4. Orphans: known slug with no inbound reference.
echo "== Orphans (no inbound [[link]]) =="
while IFS= read -r s; do
  [ -z "$s" ] && continue
  printf '%s\n' "$REFS" | grep -qxF "$s" || echo "ORPHAN  $s"
done < <(printf '%s\n' "$SLUGS")

echo "== $dangling dangling link(s) =="
[ "$dangling" -eq 0 ]

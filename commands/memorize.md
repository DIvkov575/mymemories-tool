---
description: Save a durable fact to the shared mymemories store for the current project and sync it (git pull -> write -> commit -> push).
---

Persist one durable fact into this project's mymemories partition and sync it to
the central git repo, so both Claude Code and Codex see it in future sessions.

Use the deterministic `mymem save` command (no hand-written frontmatter, no
manual git — `mymem save` pulls, writes the fact with correct frontmatter,
regenerates `MEMORY.md`, commits, and pushes). `${CLAUDE_PLUGIN_ROOT}` is the
repo root where `mymem` lives.

## When to save (be selective)

Only durable, reusable facts: a user preference or correction, a hard-won project
decision, a non-obvious constraint. NOT task status, restated context, or things
obvious from the code. When in doubt, don't.

## Steps

1. If `$ARGUMENTS` is non-empty, that's the fact to save. Otherwise infer it from
   the recent conversation and show the user the proposed memory before writing.
2. Pick a kebab-case slug and a `--type` (user | feedback | project | reference).
   Write the body compressed and technical (lead with the fact; for
   feedback/project add a `**Why:**` and `**How to apply:**` line).
3. Run (partition auto-resolves from the current project):
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/mymem" --provider claude save <slug> \
     --type <type> --description "<one-line index hook>" \
     --content "<the fact body>"
   ```
   For a long body, pipe it via stdin instead of `--content`:
   ```bash
   printf '%s' "<fact body>" | python3 "${CLAUDE_PLUGIN_ROOT}/mymem" --provider claude save <slug> --type project --description "..."
   ```
4. Report the saved slug and partition. If it reports "could not resolve a
   partition", this project isn't linked — run `python3 "${CLAUDE_PLUGIN_ROOT}/mymem" install`.

Flags: `--partition <name>` to override auto-resolution, `--dry-run` to preview,
`--no-push` to commit locally only.

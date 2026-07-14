---
name: memorize
description: "Save a durable fact to the shared mymemories store for the current project and sync it (git pull -> write -> commit -> push). Use when the user asks to remember/memorize something, or when a durable preference, decision, or non-obvious constraint emerges that future sessions should keep. Non-forcing: only save durable, reusable facts."
---

# memorize — save a fact to the shared memory store (Codex)

Persist one durable fact into this project's mymemories partition and sync it to
the central git repo, so both Codex and Claude Code see it in future sessions.

Use the deterministic `mymem save` command (no LLM, no hand-written frontmatter,
no manual git). Let `REPO` be the mymemories-tool repo root (default
`~/workplace/mymemories-tool`).

## When to save (be selective)

Only durable, reusable facts: a user preference or correction, a hard-won project
decision, a non-obvious constraint. NOT task status, restated context, or things
obvious from the code. When in doubt, don't.

## How

1. Pick a kebab-case slug and a `--type` (user | feedback | project | reference).
2. Write the fact body compressed and technical (lead with the fact; for
   feedback/project add a `**Why:**` and `**How to apply:**` line).
3. Run (the partition is resolved from the current project automatically):
   ```bash
   python3 "$REPO/mymem" --provider codex save <slug> \
     --type feedback --description "<one-line index hook>" \
     --content "<the fact body>"
   ```
   Or pipe a longer body via stdin instead of `--content`:
   ```bash
   printf '%s' "<fact body>" | python3 "$REPO/mymem" --provider codex save <slug> --type project --description "..."
   ```
4. `mymem save` pulls, writes `<partition>/<slug>.md`, regenerates `MEMORY.md`,
   commits, and pushes. Report the saved slug and partition.

Flags: `--partition <name>` to override auto-resolution, `--dry-run` to preview,
`--no-push` to commit locally only. If it reports "could not resolve a
partition", this project isn't linked yet — run `python3 "$REPO/mymem" --provider codex install`.

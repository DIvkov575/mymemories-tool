---
name: memory-consolidation
description: "Consolidate ('dream over') this project's persistent memory — reflect on recent Codex session transcripts and curate the memory partition (add durable facts, augment, supersede contradictions, merge duplicates). Use when the user asks to consolidate/curate/clean up memory, 'dream', or run the memory pass. Non-forcing: most runs propose little or nothing."
---

# Memory consolidation ("dream") — Codex

Reflect on recent Codex session transcripts and curate the current project's
memory partition using the provider-agnostic `mymem dream` command with the
Codex provider.

**Non-forcing.** The bar to save is high; most runs propose little or nothing,
and a run that saves nothing is correct. Never force ADDs.

## How it works

Two passes: **PROPOSE** — `codex exec` reads recent transcripts (from
`~/.codex/sessions/**/rollout-*.jsonl`, filtered to this project's cwd) + the
entire current partition and emits a JSON op list (`ADD/UPDATE/SUPERSEDE/MERGE/
NOOP`), writing nothing. **APPLY** — deterministic code validates each op
(evidence required, importance floor, destructive budget, soft-delete, path
confinement, scoped commit) and applies survivors, regenerates `MEMORY.md`,
commits + pushes. The model plans; code executes.

## Steps

Let `REPO` be the mymemories repo root (where `mymem` lives; default
`~/workplace/mymemories-tool`).

1. **Always dry-run first:**
   ```bash
   python3 "$REPO/mymem" --provider codex dream --partition <partition> --dry-run
   ```
   Omit `--partition` for all; add `--since YYYY-MM-DD` to widen the window.
2. **Show the user** the op count and each op's type/slug/importance. All NOOP →
   say so plainly.
3. **Apply only if the user is happy:**
   ```bash
   python3 "$REPO/mymem" --provider codex dream --partition <partition>
   ```
   Prefix `DREAM_NO_PUSH=1` to commit locally without pushing.
4. **Report** what was committed (one git commit per partition; `git revert`-able).

## Tuning (env vars)

| var | default | effect |
|---|---|---|
| `DREAM_IMPORTANCE_FLOOR` | `6` | lower to save more; raise to save less |
| `DREAM_MAX_DESTRUCTIVE` | `2` | max SUPERSEDE+MERGE per partition per run |
| `MEM_HOME` | `~/workplace/mymemories` | private memories repo |

## Notes

- Codex exposes a project's memory by a pointer appended to the project's
  `AGENTS.md` (run `mymem --provider codex install` once). Unlike Claude Code
  there is no symlinked memory dir.
- Superseded/merged files are soft-deleted to `<partition>/.superseded/`.

---
name: memory-consolidation
description: "Consolidate ('dream over') this project's persistent memory — reflect on recent session transcripts and curate the memory partition (add durable facts, augment, supersede contradictions, merge duplicates). Use when the user asks to consolidate/curate/clean up memory, 'dream', run the memory pass, or review what recent sessions should be remembered. Non-forcing: most runs propose little or nothing."
user-invocable: true
allowed-tools:
  - Bash
  - Read
---

# Memory consolidation ("dream")

Reflect on recent session transcripts and curate the current project's memory
partition using the provider-agnostic `mymem dream` command. It is the local
analogue of Anthropic's Claude "Dreams": an agent reviewing past sessions to keep
memory fresh instead of letting it decay.

**Non-forcing.** The bar to save is high; most runs propose little or nothing, and
a run that saves nothing is correct. Never pressure it to save more than the
transcripts genuinely warrant.

## How it works

Two passes: **PROPOSE** — the provider's own model (here `claude -p`) reads recent
transcripts + the entire current partition and emits a JSON op list
(`ADD/UPDATE/SUPERSEDE/MERGE/NOOP`), writing nothing. **APPLY** — deterministic
code validates each op (evidence required, importance floor, destructive budget,
soft-delete, path confinement, per-partition-scoped commit) and applies survivors,
regenerates `MEMORY.md`, commits + pushes. The model plans; code executes.

## Steps

Let `REPO` be the plugin repo root (two levels up from `${CLAUDE_PLUGIN_ROOT}`,
i.e. `${CLAUDE_PLUGIN_ROOT}/../..`).

1. **Always dry-run first:**
   ```bash
   python3 "$REPO/mymem" --provider claude dream --partition <partition> --dry-run
   ```
   Omit `--partition` for all partitions; add `--since YYYY-MM-DD` to widen the window.
2. **Show the user** the op count and each op's type/slug/importance. If it's all
   NOOP, say so plainly — nothing durable to save. Do not force ADDs.
3. **Apply only if the user is happy:**
   ```bash
   python3 "$REPO/mymem" --provider claude dream --partition <partition>
   ```
   Prefix `DREAM_NO_PUSH=1` to commit locally without pushing.
4. **Report** what was committed. Each run is one git commit scoped to the
   partition — reversible with `git revert`.

## Tuning (env vars, prefix the command)

| var | default | effect |
|---|---|---|
| `DREAM_IMPORTANCE_FLOOR` | `6` | lower (3–4) to save more; raise to save less |
| `DREAM_MAX_DESTRUCTIVE` | `2` | max SUPERSEDE+MERGE per partition per run |
| `DREAM_MODEL` | `sonnet` | model for the headless call |
| `MEM_HOME` | `~/workplace/mymemories` | private memories repo |

## Notes

- The proposer is a non-deterministic LLM: op count varies run to run. The
  importance floor is a hard quality gate, not a fixed count cap.
- Superseded/merged files are soft-deleted to `<partition>/.superseded/`.
- See `DREAM.md` in the repo root for the full method, guards, and sources.

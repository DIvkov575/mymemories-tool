# Dream — autonomous overnight memory consolidation

`dream.py` is an optional add-on to mymemories. Once a night it reflects on the
day's session transcripts and **curates each project's memory partition on its
own** — adding durable new facts, augmenting existing ones, superseding facts
the transcript contradicts, and merging duplicates. No human in the loop.

It is the local, file-based analogue of Anthropic's Claude "Dreams" — an agent
reflecting on past sessions to keep its memory fresh instead of letting it decay.

## The method (and why)

Grounded in the published consolidation literature, adapted to a small file store:

- **Two passes, separated.** A **propose** pass asks an LLM (headless `claude -p`)
  to read the corpus + the *entire* current partition and emit a structured list
  of edit operations — it writes nothing. An **apply** pass is deterministic
  Python that validates every op against hard guards and applies the survivors.
  The model never touches the filesystem. *(Mem0's extract→decide loop; the
  propose/apply split is the autonomous-safety separation.)*

- **Operation schema:** `ADD / UPDATE / SUPERSEDE / MERGE / NOOP`. Mem0's four
  operations plus explicit `MERGE`, since duplication is the dominant failure
  mode across every system surveyed.

- **Retrieve-before-write, without embeddings.** Partitions hold ~5–20 atomic
  facts, so the whole partition is handed to the model as context. For a store
  this small that is cheaper *and* strictly more accurate than a top-k vector
  search — and it keeps mymemories free of the embedding stack.

- **Guards (autonomous safeguards):**
  - **Evidence required** — every mutating op must cite the session id it came
    from; unsourced ops are rejected. *(Generative Agents' evidence citation.)*
  - **Importance floor** — ADDs below `DREAM_IMPORTANCE_FLOOR` (default 3, scale
    1–10) are dropped. The main anti-bloat dial. *(Generative Agents poignancy.)*
  - **Per-run destructive budget** — at most `DREAM_MAX_DESTRUCTIVE` (default 3)
    SUPERSEDE+MERGE ops per partition per run, bounding blast radius.
  - **Soft delete** — superseded/merged files move to `<partition>/.superseded/`,
    never `rm`. Combined with the git commit, fully reversible. *(Mem0g mark-invalid.)*
  - **Path confinement** — slugs must be plain kebab/snake; no `/` or `..`.
  - **Information-gain UPDATE** — the prompt forbids UPDATE that merely rewords.
  - **Scoped commit** — each run commits ONLY the partition it touched (never
    `git add -A`), so unrelated uncommitted memories are never swept in.
  - **Deterministic index** — `MEMORY.md` is regenerated from frontmatter every
    run, so the index can't drift from the files.

- **Cadence.** Nightly cron (the "dreaming" batch). A per-partition watermark in
  `.dream-state.json` means each run only reflects on transcripts modified since
  the last run, so re-runs are cheap and idempotent.

## Install

```bash
./install-dream.sh                     # nightly at 03:30
DREAM_HOUR=4 DREAM_MIN=0 ./install-dream.sh
./install-dream.sh --remove            # uninstall the cron job
```

## Run by hand

```bash
python3 dream.py --dry-run                       # propose for all partitions, write nothing
python3 dream.py --partition workplace --dry-run # one partition
python3 dream.py --partition workplace           # real: apply + commit + push
python3 dream.py --since 2026-07-01              # override the watermark
```

## Tuning (env vars)

| var | default | effect |
|---|---|---|
| `DREAM_MODEL` | `sonnet` | model alias for `claude -p` |
| `DREAM_IMPORTANCE_FLOOR` | `3` | raise to 5–6 for a stricter, lower-volume store |
| `DREAM_MAX_DESTRUCTIVE` | `3` | max SUPERSEDE+MERGE per partition per run |
| `DREAM_CORPUS_CHARS` | `80000` | cap on transcript chars fed per partition |
| `DREAM_NO_PUSH` | unset | commit locally but don't `git push` |
| `MEM_HOME` / `CLAUDE_HOME` | `~/workplace/mymemories` / `~/.claude` | locations |

## Recovering a dreamed edit

Every run is one git commit scoped to a single partition — `git revert` or
`git reset` it. Superseded files also sit in `<partition>/.superseded/` named
`<slug>.<timestamp>.md`. Logs are in `<MEM_HOME>/.dream-logs/<date>.log`.

## Sources

Mem0 (arXiv:2504.19413) · Generative Agents (arXiv:2304.03442) · Reflexion
(arXiv:2303.11366) · MemGPT/Letta (arXiv:2310.08560) · A-MEM (arXiv:2502.12110) ·
Anthropic memory tool (`memory_20250818`) + context-engineering guidance.

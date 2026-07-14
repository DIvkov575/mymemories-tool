# mymemories-tool

Provider-agnostic **persistent, per-project memory** for coding agents, backed by
one central git repo. Works with **Claude Code** and **Codex** from the same core.
This is the public tooling; your actual memories live in a separate private repo
this tool reads and writes.

Two things, and nothing else: **central sync** + **lazy load** — plus an optional,
hand-invoked **consolidation ("dream")** pass.

## Architecture

```
memcore/            neutral core
  store.py          MEM_HOME, manifest, partitions, fact read/write, MEMORY.md, git
  dreamlib/         VENDORED single-source reflection engine + agent backends
                    (shared with the standalone `dreams` tool: github.com/DIvkov575/dreams)
  providers.py      thin adapters: partition transcripts + harness memory exposure
  dream.py          thin adapter: partition <-> dreamlib.engine (propose/apply)
  store.py, codex_native.py, codex_import.py   mymemories-specific layer
mymem               one CLI: dream | save | codex-import | link | install | providers
integrations/
  claude/           Claude Code plugin: /memorize (mymem save), SessionStart pull hook, dream skill
  codex/            Codex memorize + memory-consolidation skills, AGENTS.md pull+save reminder, hooks.json
format.md · DREAM.md
```

The reflection engine and headless-LLM/transcript backends are **single-sourced**
in `memcore/dreamlib` (vendored from the [`dreams`](https://github.com/DIvkov575/dreams)
tool). `memcore` adds only the mymemories store/partition/manifest layer on top,
so there is exactly one engine implementation.

A **provider** abstracts the only three things that differ between agents:

| | Claude Code | Codex |
|---|---|---|
| **transcripts** | `~/.claude/projects/<mangle>/*.jsonl` | `~/.codex/sessions/**/rollout-*.jsonl` (filtered by cwd) |
| **headless LLM** | `claude -p --output-format json` | `codex exec --skip-git-repo-check` |
| **memory exposure** | symlink partition into `projects/<mangle>/memory` | pointer appended to the project's `AGENTS.md` |

Everything else — the store, the dreaming algorithm, every safety guard — is
shared. Adding another agent means adding one `Provider` subclass.

## What it does

- **Central sync** — every partition is a subdir of one private git repo. On
  session start the partition is linked in and the repo is pulled
  (`git pull --ff-only`, backgrounded); `/memorize` commits and pushes.
- **Lazy load** — only the current project's `MEMORY.md` index is auto-loaded;
  leaf facts are read on demand.
- **Consolidation ("dream")** — `mymem dream` reflects on recent transcripts and
  curates a partition (add / update / supersede / merge). Non-forcing: most runs
  save little or nothing. See [DREAM.md](DREAM.md).

## Install

Clone the private memories repo (default `~/workplace/mymemories`; override with
`MEM_HOME`), then:

```bash
python3 mymem providers          # see which agents are detected
python3 mymem install            # link every partition for all available agents
```

**Claude Code** — install the plugin (`integrations/claude/`) so `/memorize`, the
SessionStart hook, and the consolidation skill load:
```
/plugin marketplace add DIvkov575/mymemories-tool
/plugin install mymemories@mymemories
```

**Codex** — run the Codex integration installer:
```bash
integrations/codex/install.sh    # copies the skill into ~/.codex/skills + links partitions
```

## Consolidate

Always dry-run first:

```bash
python3 mymem dream --partition <name> --dry-run     # auto-detected provider
python3 mymem --provider codex dream --partition <name> --dry-run
```

Apply by dropping `--dry-run`. Method, guards, and tuning are in [DREAM.md](DREAM.md).

## Import Codex's native memories

Codex has its own memory system (`~/.codex/memories_1.sqlite` per-session
extractions + `~/.codex/memories/*.md` consolidated docs). `mymem codex-import`
reads it (never writes to it), routes each memory to a partition by the
originating session's cwd (unroutable/global memories go to a `codex-native`
partition), and runs the batch through the SAME non-forcing consolidator — so
imported items are deduped against existing facts, quality-gated, and written in
the shared markdown format both agents lazy-load.

```bash
python3 mymem codex-import --dry-run              # preview; writes nothing
python3 mymem codex-import                        # import + commit + push
python3 mymem codex-import --partition aws-billing --dry-run
```

Imported facts carry `origin: dream` with the Codex thread id as evidence, and
lazy-load like any other memory (only `MEMORY.md` auto-loads).

## The memory format

One fact per file, frontmatter (`name`, `description`, `type`); only each
partition's `MEMORY.md` index auto-loads. See [format.md](format.md).

## License

MIT.

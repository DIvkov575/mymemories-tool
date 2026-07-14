# mymemories-tool

Provider-agnostic **persistent, per-project memory** for coding agents, backed by
one central git repo. Works with **Claude Code** and **Codex** from the same core.
This is the public tooling; your actual memories live in a separate private repo
this tool reads and writes.

Two things, and nothing else: **central sync** + **lazy load** — plus an optional,
hand-invoked **consolidation ("dream")** pass.

## Architecture

```
memcore/            neutral core — knows nothing about any specific agent
  store.py          MEM_HOME, manifest, partitions, fact read/write, MEMORY.md, git
  providers.py      the ONLY harness-specific code: Claude + Codex adapters
  dream.py          two-pass, non-forcing consolidation (provider-parameterized)
mymem               one CLI: `mymem dream|link|install|providers` (+ --provider)
integrations/
  claude/           Claude Code plugin: /memorize, SessionStart hook, dream skill
  codex/            Codex skill + install.sh
format.md · DREAM.md
```

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

## The memory format

One fact per file, frontmatter (`name`, `description`, `type`); only each
partition's `MEMORY.md` index auto-loads. See [format.md](format.md).

## License

MIT.

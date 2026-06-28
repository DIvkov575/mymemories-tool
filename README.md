# mymemories-tool

A small, self-contained toolkit that gives **Claude Code agents persistent,
per-project memory** backed by a git repo — with cross-project recall and
offline semantic search. This is the **public tooling**; your actual memories
live in a separate **private** repo that this tool reads and writes.

## What it does

Claude Code auto-loads agent memory from `~/.claude/projects/<mangled-cwd>/memory/`,
one silo per project, with no central location and no version control. This tool
inverts that: all memories live in one private git repo, and each project's
partition is *symlinked* back into the path the harness loads from.

- **Partitioned auto-load** — opening project X loads only partition X (the
  harness follows the symlink; it can't tell it isn't a real dir).
- **Centralized + versioned** — every partition is a subdir of one private repo.
- **Cross-project on demand** — any session can `Read`/`grep` another partition;
  `REGISTRY.md` lists them so the agent knows they exist.
- **Auto-symlink** — a SessionStart hook links a project the first time it's
  opened with memories, so new projects need no manual step.
- **Semantic recall** — an offline embedding index (`/recall`) finds memories by
  meaning across all partitions. No API, no network: `fastembed` (ONNX) locally.

## Tool vs. memories — the split

| | repo | visibility | holds |
|---|---|---|---|
| **Tool** | `mymemories-tool` (this) | public | scripts, hook, commands — zero personal data |
| **Memories** | `mymemories` | private | your partitions, `manifest.tsv`, `index.json` |

Every script resolves two locations:
- `TOOL_DIR` — where the script lives (self-located; clone anywhere).
- `MEM_HOME` — the private memories repo. Defaults to `~/workplace/mymemories`;
  override with the `MEM_HOME` environment variable.

## Files

```
install.sh / uninstall.sh  create / remove the partition symlinks
install-hook.sh            register SessionStart hook + install slash-commands
setup.sh                   create .venv + install fastembed (for /recall)
embed.py                   build/query the offline semantic index
autolink.sh                ensure one project is partitioned + symlinked
hooks/session-start.sh     SessionStart hook -> autolink.sh for the cwd
gen-registry.sh            regenerate REGISTRY.md + awareness headers
lint.sh                    resolve [[wiki-links]]; report dangling links + orphans
commands/*.md              /memorize + /recall (copied to ~/.claude/commands/)
format.md                  compressed/technical memory format convention
```

## Install on a new device

```bash
# 1. the private memories repo (must be at MEM_HOME; default path shown)
git clone <your-private-memories-remote> ~/workplace/mymemories

# 2. this public tool (clone anywhere)
git clone https://github.com/DIvkov575/mymemories-tool ~/workplace/mymemories-tool
cd ~/workplace/mymemories-tool

./install.sh         # symlink partitions into ~/.claude/projects
./install-hook.sh    # register SessionStart hook + install /memorize, /recall
./setup.sh           # create .venv + install fastembed
python3 embed.py update   # build the embedding index (downloads ~130MB model once)
```

If your memories repo is somewhere else, set `MEM_HOME` (e.g.
`MEM_HOME=~/mem ./install.sh`) for every command, or edit the default in the
scripts.

## Add a project

1. In the memories repo: `mkdir <partition>` and add memory `.md` files (one
   fact each, with a `name:` slug in frontmatter — see `format.md`).
2. Add a line to `<MEM_HOME>/manifest.tsv`: `<partition><TAB><path-relative-to-$HOME>`.
3. From the tool: `./gen-registry.sh && ./install.sh && ./lint.sh`
4. `python3 embed.py update`, then commit + push the memories repo.

Or just open the project and let the SessionStart hook auto-link it (if it
already has memories), then `/memorize`.

## Conventions

- **One fact per file.** Frontmatter `name:` is the slug; link with `[[slug]]`.
- **Typed links** (optional): `[[supersedes:slug]]`, `[[pivoted-to:slug]]`,
  `[[because:slug]]`. `lint.sh` resolves the slug after the last `:`.
- **Write liberally; load lazily.** Only `MEMORY.md` indexes auto-load. Leaf
  facts are read on demand. Use `superseded-by` instead of deleting duplicates.
- `cozempic_digest.md` is plugin-managed and gitignored — never a real memory.

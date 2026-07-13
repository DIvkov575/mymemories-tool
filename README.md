# mymemories-tool

A small, self-contained toolkit that gives **Claude Code agents persistent,
per-project memory** backed by one central git repo. This is the **public
tooling**; your actual memories live in a separate **private** repo that this
tool reads and writes.

It does exactly two things — **central sync** and **lazy load** — and nothing
else. No semantic index, no link linter, no cross-partition registry.

## What it does

Claude Code auto-loads agent memory from `~/.claude/projects/<mangled-cwd>/memory/`,
one silo per project, with no central location and no version control. This tool
inverts that: all memories live in one private git repo, and each project's
partition is *symlinked* back into the path the harness loads from.

- **Central sync** — every partition is a subdir of one private git repo. The
  SessionStart hook pulls it down (`git pull --ff-only`, backgrounded); `/memorize`
  commits and pushes it up. Same memories on every device.
- **Lazy load** — opening project X symlinks in partition X, and the harness
  auto-loads only that partition's `MEMORY.md` index. Leaf facts are read on
  demand; other projects' partitions aren't loaded at all (but stay `Read`/`grep`-able).
- **Auto-symlink** — the SessionStart hook links a project the first time it's
  opened with memories, so new projects need no manual step.

## Tool vs. memories — the split

| | repo | visibility | holds |
|---|---|---|---|
| **Tool** | `mymemories-tool` (this) | public | scripts, hook, command — zero personal data |
| **Memories** | `mymemories` | private | your partitions + `manifest.tsv` |

Every script resolves two locations:
- `TOOL_DIR` — where the script lives (self-located; clone anywhere).
- `MEM_HOME` — the private memories repo. Defaults to `~/workplace/mymemories`;
  override with the `MEM_HOME` environment variable.

## Files

```
install.sh / uninstall.sh  create / remove the partition symlinks
install-hook.sh            register SessionStart hook + install /memorize command
autolink.sh                ensure one project is partitioned + symlinked
hooks/session-start.sh     SessionStart hook -> autolink + git pull --ff-only
commands/memorize.md       /memorize (copied to ~/.claude/commands/)
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
./install-hook.sh    # register SessionStart hook + install /memorize
```

If your memories repo is somewhere else, set `MEM_HOME` (e.g.
`MEM_HOME=~/mem ./install.sh`) for every command, or edit the default in the
scripts.

## Add a project

1. In the memories repo: `mkdir <partition>` and add memory `.md` files (one
   fact each, with a `name:` slug in frontmatter — see `format.md`).
2. Add a line to `<MEM_HOME>/manifest.tsv`: `<partition><TAB><path-relative-to-$HOME>`.
3. From the tool: `./install.sh`, then commit + push the memories repo.

Or just open the project and let the SessionStart hook auto-link it (if it
already has memories), then `/memorize`.

## Conventions

- **One fact per file.** Frontmatter `name:` is the slug (see `format.md`).
- **Write liberally; load lazily.** Only `MEMORY.md` indexes auto-load. Leaf
  facts are read on demand. Overwrite/delete stale files — don't accumulate cruft.
- `cozempic_digest.md` is plugin-managed and gitignored — never a real memory.

---
description: Save a compressed, technical memory to the central mymemories repo for the current project, then push.
---

Save what the user asked to remember as a persistent memory.

Paths: the TOOL (scripts) lives in `~/workplace/mymemories-tool`; your private
MEMORIES live in `~/workplace/mymemories`.

Steps:
1. Determine the current project's partition: run `readlink ~/.claude/projects/<mangled-cwd>/memory` — if it resolves into `~/workplace/mymemories/<partition>`, that's the target dir. If it is NOT a symlink into the memories repo, tell the user this project isn't installed and offer to run `~/workplace/mymemories-tool/install.sh` (after adding it to `~/workplace/mymemories/manifest.tsv`).
2. Read `~/workplace/mymemories-tool/format.md` and follow it EXACTLY: lead with the fact, commands verbatim, drop narration/dates/session-ids.
3. If `$ARGUMENTS` is non-empty, that is the fact to save. Otherwise infer the fact from the recent conversation and show the user the proposed memory before writing.
4. Pick a kebab-case `name:` slug and `type:` (user|feedback|project|reference). Write `<partition>/<slug>.md` (under `~/workplace/mymemories`) with the frontmatter from format.md.
5. Add the one-line pointer to `<partition>/MEMORY.md` (this index is what auto-loads; leaf facts load lazily on demand).
6. Push the memories repo up:
   ```bash
   cd ~/workplace/mymemories && git add -A && git commit -m "mem: <slug>" && git push
   ```
7. Report the saved slug and partition.

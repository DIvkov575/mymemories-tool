---
description: Save a compressed, technical memory to the central mymemories repo for the current project.
---

Save what the user asked to remember as a persistent memory.

Paths: the TOOL (scripts) lives in `~/workplace/mymemories-tool`; your private
MEMORIES live in `~/workplace/mymemories`.

Steps:
1. Determine the current project's partition: run `readlink ~/.claude/projects/<mangled-cwd>/memory` — if it resolves into `~/workplace/mymemories/<partition>`, that's the target dir. If it is NOT a symlink into the memories repo, tell the user this project isn't installed and offer to run `~/workplace/mymemories-tool/install.sh` (after adding it to `~/workplace/mymemories/manifest.tsv`).
2. Read `~/workplace/mymemories-tool/format.md` and follow it EXACTLY. The memory MUST be compressed and technical: lead with the fact, commands verbatim, drop narration/dates/session-ids.
3. If `$ARGUMENTS` is non-empty, that is the fact to save. Otherwise infer the fact from the recent conversation and show the user the proposed memory before writing.
4. Pick a kebab-case `name:` slug and `type:` (user|feedback|project|reference). Write `<partition>/<slug>.md` (under `~/workplace/mymemories`) with the frontmatter from format.md.
5. Add the one-line pointer to `<partition>/MEMORY.md`.
6. Run `~/workplace/mymemories-tool/lint.sh` and fix any dangling links it reports.
7. Update the embedding index for the new file (incremental, cheap):
   ```bash
   python3 ~/workplace/mymemories-tool/embed.py update
   ```
8. Commit and push the memories repo:
   ```bash
   cd ~/workplace/mymemories && git add -A && git commit -m "mem: <slug>" && git push
   ```
9. Report the saved slug and partition.

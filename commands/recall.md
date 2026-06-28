---
description: Semantically search all persisted memories (offline embedding search) and load the most relevant.
---

Search persisted memories by meaning, across ALL partitions.

Steps:
1. Run the offline semantic search with the user's query (`$ARGUMENTS`). The script lives in the tool repo; it reads/writes the index in the private memories repo:
   ```bash
   python3 ~/workplace/mymemories-tool/embed.py query "$ARGUMENTS"
   ```
2. The output is ranked `score  partition/file.md` lines (paths relative to `~/workplace/mymemories`). Read the top 1-3 files whose score is meaningfully high (> ~0.4) with the Read tool to load their full content.
3. Answer the user's question using those memories. Cite which memory (partition/slug) each fact came from.
4. If the top score is low (< ~0.4), say no strongly-relevant memory exists rather than forcing a weak match.

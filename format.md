# Memory format (compressed, technical)

Every memory file is one fact. Optimize for token-efficient recall, not prose.

## Frontmatter (required)
```
---
name: <kebab-slug>            # unique; matches the filename
description: <one dense line> # used for the MEMORY.md index hook
type: user|feedback|project|reference
---
```

## Body rules
- Lead with the fact in <=2 lines. No preamble ("In this session we...").
- Imperative/declarative, not narrative. Commands verbatim in backticks.
- feedback/project: one `**Why:**` line + one `**How:**` line, each <=1 sentence.
- Drop: dates unless load-bearing, session IDs, hedging, restated context.
- Duplicate/outdated? Overwrite or delete the old file — don't accumulate cruft.

## Index line (MEMORY.md)
`- [Title](file.md) — <8-12 word hook>`

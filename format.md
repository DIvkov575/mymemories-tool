# Memory format (compressed, technical)

Every memory file is one fact. Optimize for token-efficient recall, not prose.

## Frontmatter (required)
```
---
name: <kebab-slug>           # unique; this is the [[link]] target
description: <one dense line> # used for index + recall relevance
type: user|feedback|project|reference
---
```

## Body rules
- Lead with the fact in <=2 lines. No preamble ("In this session we...").
- Imperative/declarative, not narrative. Commands verbatim in backticks.
- feedback/project: one `**Why:**` line + one `**How:**` line, each <=1 sentence.
- Link related memories with [[slug]] (and typed [[supersedes:slug]] / [[pivoted-to:slug]]).
- Drop: dates unless load-bearing, session IDs, hedging, restated context.
- Supersede instead of duplicate: new file + mark old `[[superseded-by:new-slug]]`.

## Index line (MEMORY.md)
`- [Title](file.md) — <8-12 word hook>`

"""memcore.dream — provider-agnostic memory consolidation ("dreaming").

Reflect on recent session transcripts and curate a project's memory partition:
ADD / UPDATE / SUPERSEDE / MERGE / NOOP. Two passes, deliberately separated:

  1. PROPOSE — a provider's LLM reads the corpus + the WHOLE current partition
     and emits a structured op list. It writes nothing.
  2. APPLY   — this module validates every op against hard guards and applies
     the survivors, regenerates MEMORY.md, and commits. The LLM never touches
     the filesystem.

NON-FORCING by design: the bar to save is high, and a run that saves nothing is
the correct, expected outcome. DREAM_IMPORTANCE_FLOOR (default 6) is the dial.

Grounded in Mem0 (arXiv:2504.19413) op schema + retrieve-before-write, Generative
Agents (arXiv:2304.03442) importance + evidence citation, Reflexion (2303.11366)
bounded edits, Anthropic memory-tool guidance (soft-delete, path confinement).
"""
import os, re, json
from . import store

IMPORTANCE_FLOOR = int(os.environ.get("DREAM_IMPORTANCE_FLOOR", "6"))
MAX_DESTRUCTIVE = int(os.environ.get("DREAM_MAX_DESTRUCTIVE", "2"))


def log(msg):
    print(f"[dream] {msg}", flush=True)


PROMPT = """You are the memory-consolidation ("dreaming") pass for an AI coding \
assistant. You reflect on recent session transcripts and curate a project's \
long-term memory: a set of atomic, one-fact-each markdown files.

Emit a JSON object with an "operations" list. Follow the schema EXACTLY. Output \
ONLY the JSON object — no prose, no markdown fences.

## Your default answer is NOOP. Do not force memories.
Most runs should produce an empty or near-empty operations list. Saving nothing
is a SUCCESS, not a failure — never invent work to look useful. Only propose an
edit when a fact clears a HIGH bar (below). When in doubt, NOOP.

## Operations (one per candidate fact; choose the single best op)
- NOOP      — nothing clears the bar. Expected outcome; use it freely.
- ADD       — a genuinely new, durable, reusable fact with no equivalent stored.
- UPDATE    — an existing fact needs augmenting; ONLY if your new content adds
              real information (never to reword, reformat, or shorten).
- SUPERSEDE — the transcript CLEARLY CONTRADICTS an existing fact; replace it.
- MERGE     — two or more existing facts are near-duplicates; consolidate them.

## The bar for saving (be STRICT — unwanted bloat is worse than a missed fact)
A fact is worth saving ONLY if ALL hold:
1. Durable — still true and useful weeks from now (not this session's task state).
2. Non-obvious — not derivable from the code, git history, or an existing memory.
3. Reusable — it would change how a future session behaves.
Good: a user preference/correction, a hard-won project decision, a non-obvious
constraint. Bad (always NOOP): task status, what was done this session, restated
context, transient chatter, anything an existing fact already covers.
- One fact per memory. Compressed and technical. Lead with the fact. Commands
  verbatim in backticks. For feedback/project facts add a `**Why:**` line and a
  `**How to apply:**` line.

## Hard rules
- Every ADD/UPDATE/SUPERSEDE/MERGE MUST cite `evidence` = the SESSION id it came
  from (see the ===== SESSION <id> ===== headers). Unsourced ops are rejected.
- `importance` is 1-10. ADDs below {floor} are dropped downstream — so if a fact
  isn't clearly a {floor}+, emit NOOP instead of a low-importance ADD.
- On contradiction, the MORE RECENT information wins (transcripts are newest-first).
- A quiet run that saves nothing is correct. Prefer NOOP.

## Existing memory in partition "{partition}"
{existing}

## Recent session transcripts (newest first)
{corpus}

## Output schema
{{"operations": [
  {{"op":"ADD","slug":"kebab-slug","type":"feedback|project|user|reference",
    "description":"one dense line for the index","content":"the fact body (markdown)",
    "importance":7,"evidence":"<session-id>","reason":"why worth keeping"}},
  {{"op":"UPDATE","target":"existing-slug","content":"new full body",
    "importance":6,"evidence":"<session-id>","reason":"..."}},
  {{"op":"SUPERSEDE","target":"existing-slug","slug":"new-slug","type":"...",
    "description":"...","content":"...","importance":7,"evidence":"<session-id>","reason":"..."}},
  {{"op":"MERGE","targets":["slug-a","slug-b"],"slug":"merged-slug","type":"...",
    "description":"...","content":"...","importance":6,"evidence":"<session-id>","reason":"..."}},
  {{"op":"NOOP","reason":"nothing durable this run"}}
]}}"""


def _render_existing(facts):
    if not facts:
        return "(empty — no memories yet)"
    return "\n".join(
        f"### [{f['slug']}] type={f['type']}\ndescription: {f['description']}\n{f['content']}\n"
        for f in facts
    )


def parse_ops(text):
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        log("  no JSON object in model reply")
        return []
    try:
        obj = json.loads(text[start:end + 1])
    except ValueError as e:
        log(f"  JSON parse error: {e}")
        return []
    ops = obj.get("operations", []) if isinstance(obj, dict) else []
    return ops if isinstance(ops, list) else []


def propose(provider, partition, facts, corpus, model=None):
    prompt = PROMPT.format(partition=partition, existing=_render_existing(facts),
                           corpus=corpus or "(no new transcripts)", floor=IMPORTANCE_FLOOR)
    try:
        reply = provider.run_llm(prompt, model=model)
    except Exception as e:  # noqa: BLE001 — unattended; degrade to no-op
        log(f"  propose FAILED ({e.__class__.__name__}: {e}); skipping partition")
        return []
    return parse_ops(reply)


def apply_ops(partition, ops, existing_slugs, stamp, dry_run):
    """Validate + apply ops under hard guards. Returns a changelog list."""
    changelog, destructive_used = [], 0

    def note(kind, detail):
        changelog.append(f"{kind}: {detail}")
        log(f"  {kind}: {detail}")

    for op in ops:
        if not isinstance(op, dict):
            continue
        kind = (op.get("op") or "").upper()
        if kind == "NOOP":
            continue
        if kind in ("ADD", "UPDATE", "SUPERSEDE", "MERGE") and not op.get("evidence"):
            note("REJECT", f"{kind} {op.get('slug') or op.get('target')} — no evidence")
            continue

        if kind == "ADD":
            slug = op.get("slug", "")
            if not store.safe_slug(slug):
                note("REJECT", f"ADD — unsafe slug {slug!r}"); continue
            if int(op.get("importance", 0)) < IMPORTANCE_FLOOR:
                note("SKIP", f"ADD {slug} — importance<{IMPORTANCE_FLOOR}"); continue
            if slug in existing_slugs:
                note("SKIP", f"ADD {slug} — slug exists (dedup)"); continue
            note("ADD", f"{slug} (imp={op.get('importance')})")
            if not dry_run:
                store.write_fact(partition, slug, op.get("type", "reference"),
                                 op.get("description", ""), op.get("content", ""), op.get("evidence", ""))
                existing_slugs.add(slug)

        elif kind == "UPDATE":
            target = op.get("target", "")
            if target not in existing_slugs:
                note("REJECT", f"UPDATE — unknown target {target!r}"); continue
            note("UPDATE", f"{target}")
            if not dry_run:
                cur = next((f for f in store.read_partition(partition) if f["slug"] == target), None)
                store.write_fact(partition, target,
                                 op.get("type", cur["type"] if cur else "reference"),
                                 op.get("description", cur["description"] if cur else ""),
                                 op.get("content", ""), op.get("evidence", ""))

        elif kind in ("SUPERSEDE", "MERGE"):
            if destructive_used >= MAX_DESTRUCTIVE:
                note("SKIP", f"{kind} — destructive budget ({MAX_DESTRUCTIVE}) exhausted"); continue
            targets = op.get("targets") or ([op["target"]] if op.get("target") else [])
            targets = [t for t in targets if t in existing_slugs]
            if not targets:
                note("REJECT", f"{kind} — no valid targets"); continue
            slug = op.get("slug", "")
            if not store.safe_slug(slug):
                note("REJECT", f"{kind} — unsafe new slug {slug!r}"); continue
            note(kind, f"{targets} -> {slug}")
            if not dry_run:
                for t in targets:
                    store.soft_delete(partition, t, stamp); existing_slugs.discard(t)
                store.write_fact(partition, slug, op.get("type", "reference"),
                                 op.get("description", ""), op.get("content", ""), op.get("evidence", ""))
                existing_slugs.add(slug)
            destructive_used += 1
        else:
            note("REJECT", f"unknown op {kind!r}")

    return changelog


def consolidate(provider, partition, project_abs, since_ts, stamp, dry_run, model=None, push=True):
    log(f"partition {partition}  (project {project_abs}, provider {provider.name})")
    if not os.path.isdir(store.partition_dir(partition)):
        log("  no partition dir; skip"); return
    corpus, sids = provider.transcripts(project_abs, since_ts)
    if not corpus.strip():
        log("  no new transcripts since last run; skip"); return
    log(f"  corpus: {len(sids)} session(s), {len(corpus)} chars")
    facts = store.read_partition(partition)
    ops = propose(provider, partition, facts, corpus, model=model)
    log(f"  proposed {len(ops)} op(s)")
    existing = {f["slug"] for f in facts}
    changelog = apply_ops(partition, ops, existing, stamp, dry_run)
    if dry_run:
        log("  DRY-RUN: no files written"); return
    if changelog:
        store.regen_memory_index(partition)
        msg = f"dream: consolidate {partition} ({stamp})\n\n" + "\n".join(changelog)
        if store.commit_partition(partition, msg, extra_paths=[".dream-state.json"], push=push):
            log(f"  committed {len(changelog)} change(s)" + ("" if push else " (no push)"))
    else:
        log("  no surviving ops; nothing to write")

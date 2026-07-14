"""dreamlib.engine — the non-forcing reflection engine.

Two passes, source-agnostic:
  PROPOSE — the backend's LLM reads a corpus (a session transcript OR the text
    of an existing memory store) + the target MemoryDir's current facts, and
    emits a JSON op list (ADD/UPDATE/SUPERSEDE/MERGE/NOOP). Writes nothing.
  APPLY   — deterministic code validates every op against hard guards and
    applies the survivors, regenerates the index, optionally commits.

Non-forcing: default NOOP, high bar, importance floor (default 6). A run that
writes nothing is the correct, expected outcome.

Grounded in Mem0 (op schema + retrieve-before-write), Generative Agents
(importance + evidence citation), Reflexion (bounded edits), Anthropic
memory-tool guidance (soft-delete, path confinement).
"""
import os, re, json

IMPORTANCE_FLOOR = int(os.environ.get("DREAM_IMPORTANCE_FLOOR", "6"))
MAX_DESTRUCTIVE = int(os.environ.get("DREAM_MAX_DESTRUCTIVE", "2"))


def log(msg):
    print(f"[dream] {msg}", flush=True)


PROMPT = """You are a memory-consolidation ("dreaming") pass. You reflect on \
source material and curate a long-term memory: a set of atomic, one-fact-each \
markdown files.

Emit a JSON object with an "operations" list. Follow the schema EXACTLY. Output \
ONLY the JSON object — no prose, no fences.

## Your default answer is NOOP. Do not force memories.
Most runs should produce an empty or near-empty list. Saving nothing is a
SUCCESS. Never invent work to look useful. When in doubt, NOOP.

## Operations
- NOOP      — nothing clears the bar (expected; use freely).
- ADD       — a genuinely new, durable, reusable fact with no equivalent stored.
- UPDATE    — augment an existing fact; ONLY if the new content adds real info.
- SUPERSEDE — the source CLEARLY CONTRADICTS an existing fact; replace it.
- MERGE     — two+ existing facts are near-duplicates; consolidate them.

## The bar for saving (STRICT — bloat is worse than a missed fact)
Save ONLY if ALL hold: (1) durable weeks from now, (2) non-obvious / not derivable
from the source itself, (3) reusable — would change future behavior. Good: a
preference/correction, a hard-won decision, a non-obvious constraint. Bad (NOOP):
task status, restated context, transient chatter, anything already stored.
One fact per memory, compressed, technical, lead with the fact.

## Hard rules
- Every ADD/UPDATE/SUPERSEDE/MERGE MUST cite `evidence` (the SESSION id / source
  label from the ===== headers). Unsourced ops are rejected.
- `importance` 1-10. ADDs below {floor} are dropped — if not clearly {floor}+, NOOP.
- On contradiction, the MORE RECENT information wins.

## {source_kind}: existing memory in the target
{existing}

## Source material to reflect on
{corpus}

## Output schema
{{"operations":[
  {{"op":"ADD","slug":"kebab-slug","type":"feedback|project|user|reference","description":"one dense line","content":"fact body (markdown)","importance":7,"evidence":"<id>","reason":"..."}},
  {{"op":"UPDATE","target":"existing-slug","content":"new full body","importance":6,"evidence":"<id>","reason":"..."}},
  {{"op":"SUPERSEDE","target":"existing-slug","slug":"new-slug","type":"...","description":"...","content":"...","importance":7,"evidence":"<id>","reason":"..."}},
  {{"op":"MERGE","targets":["a","b"],"slug":"merged","type":"...","description":"...","content":"...","importance":6,"evidence":"<id>","reason":"..."}},
  {{"op":"NOOP","reason":"nothing durable"}}
]}}"""


def _render_existing(facts):
    if not facts:
        return "(empty — no memories yet)"
    return "\n".join(f"### [{f['slug']}] type={f['type']}\ndescription: {f['description']}\n{f['content']}\n"
                     for f in facts)


def parse_ops(text):
    text = re.sub(r"\s*```$", "", re.sub(r"^```(?:json)?\s*", "", text.strip())).strip()
    a, b = text.find("{"), text.rfind("}")
    if a == -1 or b == -1:
        log("  no JSON object in reply"); return []
    try:
        obj = json.loads(text[a:b + 1])
    except ValueError as e:
        log(f"  JSON parse error: {e}"); return []
    ops = obj.get("operations", []) if isinstance(obj, dict) else []
    return ops if isinstance(ops, list) else []


def propose(backend, memdir, corpus, source_kind="MemoryDir", model=None):
    prompt = PROMPT.format(source_kind=source_kind, existing=_render_existing(memdir.facts()),
                           corpus=corpus or "(empty)", floor=IMPORTANCE_FLOOR)
    try:
        reply = backend.run_llm(prompt, model=model)
    except Exception as e:  # noqa: BLE001
        log(f"  propose FAILED ({e.__class__.__name__}: {e})"); return []
    return parse_ops(reply)


def apply_ops(memdir, ops, stamp, dry_run):
    from .memory import safe_slug
    changelog, destructive = [], 0
    existing = memdir.slugs()

    def note(k, d):
        changelog.append(f"{k}: {d}"); log(f"  {k}: {d}")

    for op in ops:
        if not isinstance(op, dict):
            continue
        kind = (op.get("op") or "").upper()
        if kind == "NOOP":
            continue
        if kind in ("ADD", "UPDATE", "SUPERSEDE", "MERGE") and not op.get("evidence"):
            note("REJECT", f"{kind} — no evidence"); continue

        if kind == "ADD":
            slug = op.get("slug", "")
            if not safe_slug(slug):
                note("REJECT", f"ADD — unsafe slug {slug!r}"); continue
            if int(op.get("importance", 0)) < IMPORTANCE_FLOOR:
                note("SKIP", f"ADD {slug} — importance<{IMPORTANCE_FLOOR}"); continue
            if slug in existing:
                note("SKIP", f"ADD {slug} — exists (dedup)"); continue
            note("ADD", f"{slug} (imp={op.get('importance')})")
            if not dry_run:
                memdir.write_fact(slug, op.get("type", "reference"), op.get("description", ""),
                                  op.get("content", ""), op.get("evidence", "")); existing.add(slug)

        elif kind == "UPDATE":
            target = op.get("target", "")
            if target not in existing:
                note("REJECT", f"UPDATE — unknown target {target!r}"); continue
            note("UPDATE", target)
            if not dry_run:
                cur = next((f for f in memdir.facts() if f["slug"] == target), None)
                memdir.write_fact(target, op.get("type", cur["type"] if cur else "reference"),
                                  op.get("description", cur["description"] if cur else ""),
                                  op.get("content", ""), op.get("evidence", ""))

        elif kind in ("SUPERSEDE", "MERGE"):
            if destructive >= MAX_DESTRUCTIVE:
                note("SKIP", f"{kind} — destructive budget ({MAX_DESTRUCTIVE}) exhausted"); continue
            targets = [t for t in (op.get("targets") or ([op["target"]] if op.get("target") else []))
                       if t in existing]
            if not targets:
                note("REJECT", f"{kind} — no valid targets"); continue
            slug = op.get("slug", "")
            if not safe_slug(slug):
                note("REJECT", f"{kind} — unsafe new slug {slug!r}"); continue
            note(kind, f"{targets} -> {slug}")
            if not dry_run:
                for t in targets:
                    memdir.soft_delete(t, stamp); existing.discard(t)
                memdir.write_fact(slug, op.get("type", "reference"), op.get("description", ""),
                                  op.get("content", ""), op.get("evidence", "")); existing.add(slug)
            destructive += 1
        else:
            note("REJECT", f"unknown op {kind!r}")
    return changelog

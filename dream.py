#!/usr/bin/env python3
"""dream.py — autonomous overnight memory consolidation for mymemories.

A "dreaming" pass: reflect on recent session transcripts and curate a project's
memory partition — ADD / UPDATE / SUPERSEDE / MERGE / NOOP — the way Mem0 does
(extract candidate facts -> compare against existing memories -> emit a typed
edit op per candidate), with Generative-Agents-style evidence citations and the
non-destructive safeguards Anthropic recommends for the file-based memory tool.

Two passes, deliberately separated:
  1. PROPOSE  — an LLM (headless `claude -p`) reads the corpus + the WHOLE
     current partition and emits a structured list of edit operations. It
     writes nothing.
  2. APPLY    — deterministic Python validates every op against hard guards
     (evidence required, per-run destructive-edit budget, importance floor,
     path confinement, soft-delete only) and applies the survivors, then
     regenerates MEMORY.md and commits. The LLM never touches the filesystem.

Design sources (see README): Mem0 (arXiv:2504.19413) operation schema +
retrieve-before-write; Generative Agents (arXiv:2304.03442) importance scoring
+ evidence citation; Reflexion (arXiv:2303.11366) bounded edits; Anthropic
memory-tool guidance (soft-delete, coherence, path confinement, TTL).

Retrieve-before-write is done by handing the model the ENTIRE partition rather
than a top-k vector search: partitions hold ~5-20 atomic facts, so full context
is both cheaper and strictly more accurate than an embedding index — and keeps
this tool free of the embedding stack.

Usage:
  dream.py                      # consolidate every partition in the manifest
  dream.py --partition workplace
  dream.py --dry-run            # PROPOSE only; print ops, write nothing
  dream.py --since 2026-07-01   # override the per-partition last-run watermark

Env:
  MEM_HOME       private memories repo (default ~/workplace/mymemories)
  CLAUDE_HOME    Claude Code home (default ~/.claude) — for transcript lookup
  DREAM_MODEL    model alias for `claude -p` (default "sonnet")
  DREAM_MAX_DESTRUCTIVE  per-run cap on SUPERSEDE+MERGE per partition (default 3)
  DREAM_IMPORTANCE_FLOOR  drop ADDs below this importance 1-10 (default 3)
  DREAM_CORPUS_CHARS     cap on corpus chars per partition (default 80000)
  DREAM_NO_PUSH  if set, commit but do not `git push`
"""
import sys, os, json, re, glob, subprocess, argparse, datetime

HOME = os.path.expanduser("~")
MEM_HOME = os.environ.get("MEM_HOME", os.path.join(HOME, "workplace", "mymemories"))
CLAUDE_HOME = os.environ.get("CLAUDE_HOME", os.path.join(HOME, ".claude"))
MODEL = os.environ.get("DREAM_MODEL", "sonnet")
MAX_DESTRUCTIVE = int(os.environ.get("DREAM_MAX_DESTRUCTIVE", "3"))
IMPORTANCE_FLOOR = int(os.environ.get("DREAM_IMPORTANCE_FLOOR", "3"))
CORPUS_CHARS = int(os.environ.get("DREAM_CORPUS_CHARS", "80000"))
NO_PUSH = bool(os.environ.get("DREAM_NO_PUSH"))
STATE_FILE = os.path.join(MEM_HOME, ".dream-state.json")

SKIP_FILES = {"MEMORY.md", "REGISTRY.md", "README.md", "format.md",
              "cozempic_digest.md", "museum-software-ideas.md"}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def log(msg):
    print(f"[dream] {msg}", flush=True)


def mangle(path):
    """Mangle an absolute path the way Claude Code names its projects/ dirs."""
    return re.sub(r"[^A-Za-z0-9]", "-", path)


def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, ValueError):
        return {}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def read_manifest():
    """Yield (partition, project-abs-path) from the manifest."""
    mf = os.path.join(MEM_HOME, "manifest.tsv")
    with open(mf) as f:
        for line in f:
            line = line.rstrip("\n")
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) != 2:
                continue
            partition, rel = parts
            yield partition.strip(), os.path.join(HOME, rel.strip())


SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


def safe_slug(slug):
    """Confine writes: only lowercase kebab/snake slugs, no path traversal."""
    return bool(slug) and bool(SLUG_RE.match(slug)) and "/" not in slug and ".." not in slug


# ---------------------------------------------------------------------------
# corpus assembly (the reflection input)
# ---------------------------------------------------------------------------
def extract_transcript_text(path):
    """Pull just the user/assistant natural-language turns from a .jsonl transcript."""
    out = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    obj = json.loads(line)
                except ValueError:
                    continue
                m = obj.get("message") or {}
                role = m.get("role")
                if role not in ("user", "assistant"):
                    continue
                c = m.get("content")
                if isinstance(c, str):
                    out.append(f"{role.upper()}: {c}")
                elif isinstance(c, list):
                    for b in c:
                        if isinstance(b, dict) and b.get("type") == "text":
                            out.append(f"{role.upper()}: {b.get('text', '')}")
    except OSError:
        return "", None
    sid = os.path.splitext(os.path.basename(path))[0]
    return "\n".join(out), sid


def assemble_corpus(project_abs, since_ts):
    """Concatenate conversational text from transcripts modified since `since_ts`,
    newest first, capped at CORPUS_CHARS. Returns (corpus_text, [session_ids])."""
    tdir = os.path.join(CLAUDE_HOME, "projects", mangle(project_abs))
    files = sorted(glob.glob(os.path.join(tdir, "*.jsonl")),
                   key=os.path.getmtime, reverse=True)
    chunks, sids, total = [], [], 0
    for p in files:
        if since_ts and os.path.getmtime(p) <= since_ts:
            continue
        text, sid = extract_transcript_text(p)
        if not text.strip():
            continue
        header = f"\n===== SESSION {sid} =====\n"
        piece = header + text
        if total + len(piece) > CORPUS_CHARS:
            piece = piece[: max(0, CORPUS_CHARS - total)]
        chunks.append(piece)
        sids.append(sid)
        total += len(piece)
        if total >= CORPUS_CHARS:
            break
    return "".join(chunks), sids


# ---------------------------------------------------------------------------
# current memory state
# ---------------------------------------------------------------------------
def parse_frontmatter(text):
    """Return (frontmatter_dict, body). Minimal YAML: top-level key: value only."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    fm_raw = text[3:end].strip("\n")
    body = text[end + 4:].lstrip("\n")
    fm = {}
    for line in fm_raw.split("\n"):
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if m:
            fm[m.group(1)] = m.group(2).strip().strip('"')
    return fm, body


def read_partition(partition):
    """Return list of {slug, type, description, content} for existing facts."""
    pdir = os.path.join(MEM_HOME, partition)
    facts = []
    for p in sorted(glob.glob(os.path.join(pdir, "*.md"))):
        b = os.path.basename(p)
        if b in SKIP_FILES:
            continue
        fm, body = parse_frontmatter(open(p, encoding="utf-8").read())
        facts.append({
            "slug": fm.get("name", os.path.splitext(b)[0]),
            "type": fm.get("type", fm.get("metadata", "")) or "reference",
            "description": fm.get("description", ""),
            "content": body.strip(),
            "path": p,
        })
    return facts


# ---------------------------------------------------------------------------
# PROPOSE pass
# ---------------------------------------------------------------------------
PROMPT = """You are the memory-consolidation ("dreaming") pass for an AI coding \
assistant. You reflect on recent session transcripts and curate a project's \
long-term memory: a set of atomic, one-fact-each markdown files.

Emit a JSON list of edit operations. Follow the schema EXACTLY. Output ONLY the \
JSON object, no prose, no markdown fences.

## Operations (one per candidate fact; choose the single best op)
- ADD       — a genuinely new, durable fact with no equivalent already stored.
- UPDATE    — an existing fact needs augmenting; ONLY if your new content adds
              information (never to reword or shorten).
- SUPERSEDE — the transcript CONTRADICTS an existing fact; replace it. The old
              file is soft-deleted (kept for rollback), a new one written.
- MERGE     — two or more existing facts are near-duplicates; consolidate them.
- NOOP      — nothing worth persisting (use freely; most sessions add 0-2 facts).

## What makes a good memory (be STRICT — bloat is the main failure mode)
- Durable and reusable across future sessions: user preferences, hard-won
  project decisions, non-obvious constraints, corrections the user made.
- NOT: one-off task status, things obvious from the code/git, restated context,
  transient chatter, or anything already captured by an existing fact.
- One fact per memory. Compressed and technical. Lead with the fact. Commands
  verbatim in backticks. For feedback/project facts add a `**Why:**` line and a
  `**How to apply:**` line.

## Hard rules
- Every ADD/UPDATE/SUPERSEDE/MERGE MUST cite `evidence` = the SESSION id it came
  from (see the ===== SESSION <id> ===== headers). Unsourced ops are rejected.
- `importance` is 1-10 (Generative-Agents poignancy). Mundane=2, load-bearing
  decision/correction=8+. ADDs below {floor} are dropped downstream, so don't
  bother with trivia.
- On contradiction, the MORE RECENT information wins (transcripts are newest-first).
- Prefer NOOP over a weak ADD. A quiet night is a correct outcome.

## Existing memory in partition "{partition}"
{existing}

## Recent session transcripts (newest first)
{corpus}

## Output schema
{{"operations": [
  {{"op":"ADD","slug":"kebab-slug","type":"feedback|project|user|reference",
    "description":"one dense line for the index","content":"the fact body (markdown)",
    "importance":7,"evidence":"<session-id>","reason":"why this is worth keeping"}},
  {{"op":"UPDATE","target":"existing-slug","content":"new full body",
    "importance":6,"evidence":"<session-id>","reason":"..."}},
  {{"op":"SUPERSEDE","target":"existing-slug","slug":"new-slug","type":"...",
    "description":"...","content":"...","importance":7,"evidence":"<session-id>","reason":"..."}},
  {{"op":"MERGE","targets":["slug-a","slug-b"],"slug":"merged-slug","type":"...",
    "description":"...","content":"...","importance":6,"evidence":"<session-id>","reason":"..."}},
  {{"op":"NOOP","reason":"nothing durable this run"}}
]}}"""


def render_existing(facts):
    if not facts:
        return "(empty — no memories yet)"
    out = []
    for f in facts:
        out.append(f"### [{f['slug']}] type={f['type']}\n"
                   f"description: {f['description']}\n{f['content']}\n")
    return "\n".join(out)


def propose(partition, facts, corpus):
    prompt = PROMPT.format(partition=partition, existing=render_existing(facts),
                           corpus=corpus or "(no new transcripts)", floor=IMPORTANCE_FLOOR)
    try:
        proc = subprocess.run(
            ["claude", "-p", prompt, "--output-format", "json", "--model", MODEL],
            capture_output=True, text=True, timeout=600,
            env={**os.environ, "CLAUDE_HOME": CLAUDE_HOME},
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        log(f"  propose FAILED ({e.__class__.__name__}); skipping partition")
        return []
    if proc.returncode != 0:
        log(f"  claude -p exit {proc.returncode}: {proc.stderr[:200]}")
        return []
    # `--output-format json` wraps the reply; the model's text is in .result
    raw = proc.stdout
    try:
        env = json.loads(raw)
        result = env.get("result", raw) if isinstance(env, dict) else raw
    except ValueError:
        result = raw
    return parse_ops(result)


def parse_ops(text):
    """Extract the operations list from the model's reply, tolerant of fences."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text).strip()
    # find the outermost {...}
    start = text.find("{")
    end = text.rfind("}")
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


# ---------------------------------------------------------------------------
# APPLY pass (deterministic, guarded)
# ---------------------------------------------------------------------------
def write_fact(partition, slug, ftype, description, content, evidence):
    path = os.path.join(MEM_HOME, partition, f"{slug}.md")
    fm = (f"---\nname: {slug}\n"
          f"description: \"{description.replace(chr(34), chr(39))}\"\n"
          f"metadata:\n  type: {ftype}\n  origin: dream\n"
          f"  evidence: {evidence}\n---\n\n{content.strip()}\n")
    with open(path, "w", encoding="utf-8") as f:
        f.write(fm)
    return path


def soft_delete(partition, slug, stamp):
    """Move a fact out of the partition into .superseded/ (git diff is the real
    audit trail; this local copy is a belt-and-suspenders restore point)."""
    src = os.path.join(MEM_HOME, partition, f"{slug}.md")
    if not os.path.exists(src):
        return False
    graveyard = os.path.join(MEM_HOME, partition, ".superseded")
    os.makedirs(graveyard, exist_ok=True)
    os.rename(src, os.path.join(graveyard, f"{slug}.{stamp}.md"))
    return True


def title_from_slug(slug):
    return " ".join(w.capitalize() for w in re.split(r"[-_]", slug))


def regen_memory_index(partition):
    """Rebuild MEMORY.md deterministically from fact frontmatter so the index
    can never drift from the files (a real failure mode)."""
    facts = read_partition(partition)
    lines = [f"- [{title_from_slug(f['slug'])}]({f['slug']}.md) — {f['description']}"
             for f in sorted(facts, key=lambda x: x["slug"])]
    path = os.path.join(MEM_HOME, partition, "MEMORY.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + ("\n" if lines else ""))


def apply_ops(partition, ops, existing_slugs, stamp, dry_run):
    """Validate + apply ops under hard guards. Returns a changelog list."""
    changelog = []
    destructive_used = 0

    def note(kind, detail):
        changelog.append(f"{kind}: {detail}")
        log(f"  {kind}: {detail}")

    for op in ops:
        if not isinstance(op, dict):
            continue
        kind = (op.get("op") or "").upper()

        if kind == "NOOP":
            continue

        # Guard: evidence required on every mutating op.
        if kind in ("ADD", "UPDATE", "SUPERSEDE", "MERGE") and not op.get("evidence"):
            note("REJECT", f"{kind} {op.get('slug') or op.get('target')} — no evidence")
            continue

        if kind == "ADD":
            slug = op.get("slug", "")
            if not safe_slug(slug):
                note("REJECT", f"ADD — unsafe slug {slug!r}")
                continue
            if int(op.get("importance", 0)) < IMPORTANCE_FLOOR:
                note("SKIP", f"ADD {slug} — importance<{IMPORTANCE_FLOOR}")
                continue
            if slug in existing_slugs:
                note("SKIP", f"ADD {slug} — slug exists (dedup); model should UPDATE")
                continue
            note("ADD", f"{slug} (imp={op.get('importance')})")
            if not dry_run:
                write_fact(partition, slug, op.get("type", "reference"),
                           op.get("description", ""), op.get("content", ""),
                           op.get("evidence", ""))
                existing_slugs.add(slug)

        elif kind == "UPDATE":
            target = op.get("target", "")
            if target not in existing_slugs:
                note("REJECT", f"UPDATE — unknown target {target!r}")
                continue
            note("UPDATE", f"{target}")
            if not dry_run:
                # preserve type/description unless the op overrides them
                cur = next((f for f in read_partition(partition) if f["slug"] == target), None)
                write_fact(partition, target,
                           op.get("type", cur["type"] if cur else "reference"),
                           op.get("description", cur["description"] if cur else ""),
                           op.get("content", ""), op.get("evidence", ""))

        elif kind in ("SUPERSEDE", "MERGE"):
            if destructive_used >= MAX_DESTRUCTIVE:
                note("SKIP", f"{kind} — per-run destructive budget ({MAX_DESTRUCTIVE}) exhausted")
                continue
            targets = op.get("targets") or ([op["target"]] if op.get("target") else [])
            targets = [t for t in targets if t in existing_slugs]
            if not targets:
                note("REJECT", f"{kind} — no valid targets among {op.get('targets') or op.get('target')}")
                continue
            slug = op.get("slug", "")
            if not safe_slug(slug):
                note("REJECT", f"{kind} — unsafe new slug {slug!r}")
                continue
            note(kind, f"{targets} -> {slug}")
            if not dry_run:
                for t in targets:
                    soft_delete(partition, t, stamp)
                    existing_slugs.discard(t)
                write_fact(partition, slug, op.get("type", "reference"),
                           op.get("description", ""), op.get("content", ""),
                           op.get("evidence", ""))
                existing_slugs.add(slug)
            destructive_used += 1
        else:
            note("REJECT", f"unknown op {kind!r}")

    return changelog


# ---------------------------------------------------------------------------
# git
# ---------------------------------------------------------------------------
def git(*args, check=True):
    return subprocess.run(["git", "-C", MEM_HOME, *args],
                          capture_output=True, text=True, check=check)


def commit_and_push(partition, changelog, stamp):
    # Scope the commit to THIS partition (+ the run watermark) only. Never
    # `git add -A` — the repo may hold unrelated uncommitted memories from other
    # projects, and a dreaming run must not sweep them into its commit.
    git("add", "--", partition, ".dream-state.json", check=False)
    st = git("status", "--porcelain", "--", partition, check=False).stdout.strip()
    if not st:
        log("  no filesystem changes to commit")
        return
    body = "\n".join(changelog)
    msg = f"dream: consolidate {partition} ({stamp})\n\n{body}"
    # Commit only this partition + watermark by pathspec, so nothing else that
    # may be staged in the repo rides along.
    git("commit", "-q", "-m", msg, "--", partition, ".dream-state.json", check=False)
    log(f"  committed {len(changelog)} change(s)")
    if NO_PUSH:
        log("  DREAM_NO_PUSH set — not pushing")
        return
    r = git("push", check=False)
    log("  pushed" if r.returncode == 0 else f"  push failed: {r.stderr.strip()[:160]}")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def run_partition(partition, project_abs, since_ts, stamp, dry_run):
    log(f"partition {partition}  (project {project_abs})")
    if not os.path.isdir(os.path.join(MEM_HOME, partition)):
        log("  no partition dir; skip")
        return
    corpus, sids = assemble_corpus(project_abs, since_ts)
    if not corpus.strip():
        log("  no new transcripts since last run; skip")
        return
    log(f"  corpus: {len(sids)} session(s), {len(corpus)} chars")
    facts = read_partition(partition)
    ops = propose(partition, facts, corpus)
    log(f"  proposed {len(ops)} op(s)")
    existing = {f["slug"] for f in facts}
    changelog = apply_ops(partition, ops, existing, stamp, dry_run)
    if dry_run:
        log("  DRY-RUN: no files written")
        return
    if changelog:
        regen_memory_index(partition)
        commit_and_push(partition, changelog, stamp)
    else:
        log("  no surviving ops; nothing to write")


def main():
    ap = argparse.ArgumentParser(description="Autonomous memory consolidation.")
    ap.add_argument("--partition", help="only this partition")
    ap.add_argument("--dry-run", action="store_true", help="propose only; write nothing")
    ap.add_argument("--since", help="override last-run watermark (YYYY-MM-DD)")
    args = ap.parse_args()

    if not os.path.isdir(MEM_HOME):
        log(f"MEM_HOME not found: {MEM_HOME}"); sys.exit(1)

    stamp = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    state = load_state()
    since_override = None
    if args.since:
        since_override = datetime.datetime.strptime(args.since, "%Y-%m-%d").timestamp()

    # pull latest before consolidating (central sync)
    if not args.dry_run and os.path.isdir(os.path.join(MEM_HOME, ".git")):
        git("pull", "--ff-only", check=False)

    for partition, project_abs in read_manifest():
        if args.partition and partition != args.partition:
            continue
        since_ts = since_override if since_override is not None else state.get(partition)
        run_partition(partition, project_abs, since_ts, stamp, args.dry_run)
        if not args.dry_run:
            state[partition] = datetime.datetime.now().timestamp()
            save_state(state)

    log("done")


if __name__ == "__main__":
    main()

"""memcore.codex_native — read Codex's OWN memory system and import it into
the shared mymemories store as ordinary, lazy-loaded fact files.

Codex keeps native memories in two places under $CODEX_HOME (~/.codex):
  1. memories_1.sqlite -> table `stage1_outputs`: one row per session with
     `thread_id` (== rollout session uuid), `raw_memory`, `rollout_summary`,
     `rollout_slug`, usage counters, and a `selected_for_phase2` flag. This is
     the per-session extraction layer.
  2. memories/*.md : the Phase-2 consolidated markdown (raw_memories.md, plus
     any extension notes). This is the global rollup.

This module reads both, routes each item to a partition (by the session's cwd,
resolved from the rollout transcript; else a fallback global partition), and
returns candidate facts. It only READS Codex state — never writes to it.
"""
import os, glob, json, sqlite3

HOME = os.path.expanduser("~")
CODEX_HOME = os.environ.get("CODEX_HOME", os.path.join(HOME, ".codex"))


def _db_path():
    # memories_1.sqlite is the current schema; glob in case of a version bump.
    cands = sorted(glob.glob(os.path.join(CODEX_HOME, "memories_*.sqlite")))
    return cands[-1] if cands else os.path.join(CODEX_HOME, "memories_1.sqlite")


def _session_cwd(thread_id):
    """Resolve a Codex session's cwd from its rollout transcript's session_meta."""
    for p in glob.glob(os.path.join(CODEX_HOME, "sessions", "**", f"rollout-*{thread_id}*.jsonl"),
                       recursive=True):
        try:
            with open(p, encoding="utf-8") as f:
                obj = json.loads(f.readline())
            if obj.get("type") == "session_meta":
                return (obj.get("payload") or {}).get("cwd")
        except (OSError, ValueError):
            continue
    return None


def stage1_rows():
    """Yield per-session native memories from the sqlite extraction layer:
    dicts with thread_id, raw_memory, rollout_summary, slug, cwd, usage_count."""
    db = _db_path()
    if not os.path.exists(db):
        return
    try:
        # read-only; tolerate a live/locked DB (Codex may be writing)
        con = sqlite3.connect(f"file:{db}?mode=ro&immutable=1", uri=True)
    except sqlite3.Error:
        return
    try:
        cur = con.execute(
            "SELECT thread_id, raw_memory, rollout_summary, rollout_slug, "
            "usage_count, last_usage FROM stage1_outputs"
        )
        cols = [d[0] for d in cur.description]
        for row in cur.fetchall():
            r = dict(zip(cols, row))
            if not (r.get("raw_memory") or "").strip():
                continue
            r["cwd"] = _session_cwd(r["thread_id"])
            yield r
    except sqlite3.Error:
        return
    finally:
        con.close()


def consolidated_docs():
    """Yield (name, text) for the Phase-2 consolidated markdown + extension notes,
    skipping Codex scaffolding/placeholder files."""
    skip = {"phase2_workspace_diff.md"}
    placeholder = "No raw memories yet."
    for p in glob.glob(os.path.join(CODEX_HOME, "memories", "**", "*.md"), recursive=True):
        name = os.path.relpath(p, os.path.join(CODEX_HOME, "memories"))
        if os.path.basename(p) in skip:
            continue
        try:
            text = open(p, encoding="utf-8").read()
        except OSError:
            continue
        if not text.strip() or placeholder in text:
            continue
        # extension "instructions.md" files are meta, not memory content
        if name.endswith("instructions.md"):
            continue
        yield name, text


def available():
    return os.path.isdir(CODEX_HOME) and (
        os.path.exists(_db_path()) or os.path.isdir(os.path.join(CODEX_HOME, "memories"))
    )

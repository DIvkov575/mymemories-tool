"""memcore.codex_import — bridge Codex's native memories into mymemories.

Reads Codex's own memory system (memcore.codex_native), routes each native
memory to a mymemories partition by the originating session's cwd, and runs the
batch through the SAME non-forcing dream consolidation used for transcripts —
so imported memories are deduped against existing facts, quality-gated by the
importance floor, and written in the shared markdown format that BOTH Claude and
Codex lazy-load. Codex's own store is only read, never modified.

Routing:
  - stage1 rows -> partition whose manifest project == the session cwd
  - anything unroutable (no cwd match) + the Phase-2 consolidated docs ->
    a single fallback partition (default "codex-native"), created if absent.
"""
import os
from . import store, dream as dreamer, codex_native

FALLBACK_PARTITION = os.environ.get("CODEX_IMPORT_PARTITION", "codex-native")


def _partition_by_cwd(cwd):
    if not cwd:
        return None
    for part, proj in store.read_manifest():
        if os.path.realpath(proj) == os.path.realpath(cwd):
            return part
    return None


def _corpus_for_partition():
    """Group Codex native memories into per-partition corpora. Returns
    {partition: corpus_text}. Each memory becomes a labelled block whose
    'SESSION' id is the Codex thread (evidence), so the consolidator can cite it."""
    buckets = {}

    def add(part, header, body):
        buckets.setdefault(part, []).append(f"\n===== SESSION {header} =====\n{body}")

    # 1. per-session stage1 extractions -> routed by cwd
    for r in codex_native.stage1_rows():
        part = _partition_by_cwd(r.get("cwd")) or FALLBACK_PARTITION
        body = r.get("raw_memory", "").strip()
        summ = (r.get("rollout_summary") or "").strip()
        if summ:
            body += f"\n\n[rollout summary] {summ}"
        add(part, f"codex:{r['thread_id']}", body)

    # 2. Phase-2 consolidated docs -> fallback partition (they're already global)
    for name, text in codex_native.consolidated_docs():
        add(FALLBACK_PARTITION, f"codex-consolidated:{name}", text.strip())

    return {p: "".join(chunks) for p, chunks in buckets.items()}


def run(provider, stamp, dry_run, model=None, push=True, only_partition=None):
    """Import Codex native memories into partitions via the dream consolidator."""
    if not codex_native.available():
        dreamer.log("codex native memory not found; nothing to import")
        return
    corpora = _corpus_for_partition()
    if not corpora:
        dreamer.log("no Codex native memories to import (store empty)")
        return

    for partition, corpus in corpora.items():
        if only_partition and partition != only_partition:
            continue
        dreamer.log(f"codex-import -> partition {partition}  ({len(corpus)} chars)")
        pdir = store.partition_dir(partition)
        if not os.path.isdir(pdir):
            if dry_run:
                dreamer.log(f"  (would create partition dir {partition})")
            else:
                os.makedirs(pdir, exist_ok=True)
        facts = store.read_partition(partition) if os.path.isdir(pdir) else []
        # Reuse the exact non-forcing consolidation: propose ops from the native
        # memories as "corpus", then apply under all the usual guards.
        ops = dreamer.propose(provider, partition, facts, corpus, model=model)
        dreamer.log(f"  proposed {len(ops)} op(s)")
        existing = {f["slug"] for f in facts}
        changelog = dreamer.apply_ops(partition, ops, existing, stamp, dry_run)
        if dry_run:
            dreamer.log("  DRY-RUN: no files written")
            continue
        if changelog:
            store.regen_memory_index(partition)
            msg = f"codex-import: {partition} ({stamp})\n\n" + "\n".join(changelog)
            if store.commit_partition(partition, msg, extra_paths=[".dream-state.json"], push=push):
                dreamer.log(f"  committed {len(changelog)} change(s)")
        else:
            dreamer.log("  no surviving ops; nothing to write")

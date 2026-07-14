"""memcore.dream — mymemories consolidation, delegating to the shared engine.

The reflection engine (propose/apply, prompt, guards) is single-sourced in the
vendored dreamlib.engine. This module adapts it to mymemories' partition/manifest
model: it wraps a partition as a dreamlib MemoryDir and exposes the same
propose/apply_ops/consolidate/log API that mymem + codex_import already call, so
there is exactly ONE engine implementation across mymemories and the dreams tool.
"""
import os
from . import store
from .dreamlib import engine as _engine
from .dreamlib.memory import MemoryDir

# re-export knobs + log so callers keep working unchanged
log = _engine.log
IMPORTANCE_FLOOR = _engine.IMPORTANCE_FLOOR
MAX_DESTRUCTIVE = _engine.MAX_DESTRUCTIVE


def _memdir(partition):
    return MemoryDir(store.partition_dir(partition))


def propose(provider, partition, facts, corpus, model=None):
    # dreamlib.propose reads facts from the MemoryDir itself; `facts` arg kept
    # for signature compatibility with existing callers.
    return _engine.propose(provider, _memdir(partition), corpus,
                           source_kind="SESSION", model=model)


def apply_ops(partition, ops, existing_slugs, stamp, dry_run):
    # `existing_slugs` kept for signature compatibility; the engine recomputes
    # from the MemoryDir. Returns the changelog list, same as before.
    return _engine.apply_ops(_memdir(partition), ops, stamp, dry_run)


def consolidate(provider, partition, project_abs, since_ts, stamp, dry_run, model=None, push=True):
    log(f"partition {partition}  (project {project_abs}, provider {provider.name})")
    if not os.path.isdir(store.partition_dir(partition)):
        log("  no partition dir; skip"); return
    corpus, sids = provider.transcripts(project_abs, since_ts)
    if not corpus.strip():
        log("  no new transcripts since last run; skip"); return
    log(f"  corpus: {len(sids)} session(s), {len(corpus)} chars")
    ops = propose(provider, partition, None, corpus, model=model)
    log(f"  proposed {len(ops)} op(s)")
    changelog = apply_ops(partition, ops, None, stamp, dry_run)
    if dry_run:
        log("  DRY-RUN: no files written"); return
    if changelog:
        store.regen_memory_index(partition)
        msg = f"dream: consolidate {partition} ({stamp})\n\n" + "\n".join(changelog)
        if store.commit_partition(partition, msg, extra_paths=[".dream-state.json"], push=push):
            log(f"  committed {len(changelog)} change(s)" + ("" if push else " (no push)"))
    else:
        log("  no surviving ops; nothing to write")

"""dreamlib.sources — turn a --source into corpus text for the engine.

Two source kinds:
  session — one (or more) session transcripts, read via a backend. Selectable by
            'latest', a session-id substring, or a file path.
  store   — an existing memory directory (the facts themselves become the source,
            e.g. to re-consolidate / dedup / merge a store against itself).
"""
import os
from .memory import MemoryDir

CORPUS_CHARS = int(os.environ.get("DREAM_CORPUS_CHARS", "80000"))


def from_session(backend, selector="latest", n=1):
    """Return (corpus_text, label). selector: 'latest' | id-substring | path."""
    picks = []
    if selector in (None, "latest"):
        picks = backend.sessions()[:n]
    else:
        one = backend.find_session(selector)
        if one:
            picks = [one]
    if not picks:
        return "", "session:none"
    chunks, total = [], 0
    for path, sid, _mt in picks:
        text = backend.extract(path)
        if not text.strip():
            continue
        piece = f"\n===== SESSION {sid} =====\n{text}"
        if total + len(piece) > CORPUS_CHARS:
            piece = piece[:max(0, CORPUS_CHARS - total)]
        chunks.append(piece); total += len(piece)
        if total >= CORPUS_CHARS:
            break
    return "".join(chunks), f"session:{picks[0][1]}"


def from_store(path):
    """Return (corpus_text, label) built from an existing memory dir's facts."""
    md = MemoryDir(path)
    facts = md.facts()
    if not facts:
        return "", f"store:{os.path.basename(md.path)}:empty"
    chunks = [f"\n===== SOURCE {os.path.basename(md.path)} =====\n"]
    for f in facts:
        chunks.append(f"### [{f['slug']}] type={f['type']}\n{f['description']}\n{f['content']}\n")
    corpus = "".join(chunks)[:CORPUS_CHARS]
    return corpus, f"store:{os.path.basename(md.path)}"

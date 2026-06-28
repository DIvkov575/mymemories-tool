#!/usr/bin/env python3
"""Offline semantic index over the private memories repo.
Commands: update | query <text>. Incremental: only re-embeds files whose
content hash changed. Self-re-execs under the tool-local .venv so bare
`python3 embed.py` works.

Two locations are kept separate:
  TOOL_DIR  — where this script + its .venv live (this PUBLIC tool repo)
  MEM_HOME  — the PRIVATE memories repo (partitions + index.json), default
              ~/workplace/mymemories, overridable via the MEM_HOME env var."""
import sys, os, json, hashlib, glob

TOOL_DIR = os.path.dirname(os.path.abspath(__file__))

# Re-exec under the tool-local venv if present and not already active.
_VENV_PY = os.path.join(TOOL_DIR, ".venv", "bin", "python3")
# NOTE: compare without realpath() — a stdlib venv on Homebrew Python symlinks
# .venv/bin/python3 back to the shared interpreter, so realpath() would make the
# two paths identical and the guard would never fire (fastembed lives only in the
# venv's site-packages). Comparing the literal executable paths re-execs correctly.
if os.path.exists(_VENV_PY) and os.path.abspath(sys.executable) != os.path.abspath(_VENV_PY):
    os.execv(_VENV_PY, [_VENV_PY] + sys.argv)

from fastembed import TextEmbedding

MEM_HOME = os.environ.get("MEM_HOME",
                          os.path.join(os.path.expanduser("~"), "workplace", "mymemories"))
INDEX = os.path.join(MEM_HOME, "index.json")
MODEL = "BAAI/bge-small-en-v1.5"
SKIP_NAMES = {"MEMORY.md", "REGISTRY.md", "README.md", "format.md",
              "museum-software-ideas.md"}
SKIP_PARTITIONS = {"docs", "commands", "hooks"}

def memory_files():
    for p in glob.glob(os.path.join(MEM_HOME, "*", "*.md")):
        rel = os.path.relpath(p, MEM_HOME)
        partition = rel.split(os.sep)[0]
        if (os.path.basename(p) in SKIP_NAMES
                or partition in SKIP_PARTITIONS
                or "cozempic_digest" in p):
            continue
        yield p

def load_index():
    if os.path.exists(INDEX):
        with open(INDEX) as f:
            return json.load(f)
    return {}

def cmd_update():
    idx = load_index()
    model = TextEmbedding(model_name=MODEL)
    changed, texts, keys = [], [], []
    seen = set()
    for path in memory_files():
        rel = os.path.relpath(path, MEM_HOME)
        seen.add(rel)
        text = open(path, encoding="utf-8").read()
        h = hashlib.sha256(text.encode()).hexdigest()
        if idx.get(rel, {}).get("hash") == h:
            continue
        texts.append(text); keys.append((rel, h, path))
    if texts:
        vecs = list(model.embed(texts))
        for (rel, h, path), v in zip(keys, vecs):
            idx[rel] = {"hash": h, "vector": v.tolist(),
                        "partition": rel.split(os.sep)[0]}
            changed.append(rel)
    for rel in list(idx):
        if rel not in seen:
            del idx[rel]
    with open(INDEX, "w") as f:
        json.dump(idx, f)
    print(f"indexed {len(changed)} changed, {len(idx)} total")

def cmd_query(q, k=5):
    idx = load_index()
    if not idx:
        print("empty index; run: embed.py update"); return
    model = TextEmbedding(model_name=MODEL)
    qv = list(model.embed([q]))[0]
    def dot(a, b): return sum(x*y for x, y in zip(a, b))
    scored = sorted(((dot(qv, e["vector"]), rel, e["partition"])
                     for rel, e in idx.items()), reverse=True)
    for score, rel, part in scored[:k]:
        print(f"{score:.3f}  {rel}")

if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "update":
        cmd_update()
    elif len(sys.argv) >= 3 and sys.argv[1] == "query":
        cmd_query(" ".join(sys.argv[2:]))
    else:
        print("usage: embed.py update | query <text>"); sys.exit(1)

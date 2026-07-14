"""memcore.store — provider-agnostic memory store operations.

Knows nothing about Claude, Codex, or any harness. It only understands:
  - MEM_HOME: one central git repo of memory partitions
  - a partition: a subdir of atomic one-fact-each markdown files + a MEMORY.md index
  - the manifest: partition -> project-path-relative-to-$HOME

Providers (memcore.providers) handle everything harness-specific: where a
project's transcripts live, how to run an LLM, and how to expose a partition so
the harness auto-loads it. This module is the shared substrate underneath them.
"""
import os, re, glob, subprocess

HOME = os.path.expanduser("~")
MEM_HOME = os.environ.get("MEM_HOME", os.path.join(HOME, "workplace", "mymemories"))

# Files that live in a partition but are never themselves a "fact".
SKIP_FILES = {"MEMORY.md", "REGISTRY.md", "README.md", "format.md",
              "cozempic_digest.md", "museum-software-ideas.md"}

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


def mangle(path):
    """Mangle an absolute path the way Claude Code names its projects/ dirs:
    every non-alphanumeric char -> '-'. (Also used by the Claude provider.)"""
    return re.sub(r"[^A-Za-z0-9]", "-", path)


def safe_slug(slug):
    """Confine writes: lowercase kebab/snake only, no path traversal."""
    return bool(slug) and bool(SLUG_RE.match(slug)) and "/" not in slug and ".." not in slug


def manifest_path():
    return os.path.join(MEM_HOME, "manifest.tsv")


def read_manifest():
    """Yield (partition, project-abs-path) for each manifest line."""
    mf = manifest_path()
    if not os.path.exists(mf):
        return
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


def partition_dir(partition):
    return os.path.join(MEM_HOME, partition)


def parse_frontmatter(text):
    """Return (frontmatter_dict, body). Minimal YAML: top-level `key: value`."""
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
    """Return [{slug, type, description, content, path}] for existing facts."""
    facts = []
    for p in sorted(glob.glob(os.path.join(partition_dir(partition), "*.md"))):
        b = os.path.basename(p)
        if b in SKIP_FILES:
            continue
        fm, body = parse_frontmatter(open(p, encoding="utf-8").read())
        facts.append({
            "slug": fm.get("name", os.path.splitext(b)[0]),
            "type": fm.get("type", "reference"),
            "description": fm.get("description", ""),
            "content": body.strip(),
            "path": p,
        })
    return facts


def write_fact(partition, slug, ftype, description, content, evidence, origin="dream"):
    path = os.path.join(partition_dir(partition), f"{slug}.md")
    fm = (f"---\nname: {slug}\n"
          f"description: \"{description.replace(chr(34), chr(39))}\"\n"
          f"metadata:\n  type: {ftype}\n  origin: {origin}\n"
          f"  evidence: {evidence}\n---\n\n{content.strip()}\n")
    with open(path, "w", encoding="utf-8") as f:
        f.write(fm)
    return path


def soft_delete(partition, slug, stamp):
    """Move a fact into <partition>/.superseded/ instead of removing it."""
    src = os.path.join(partition_dir(partition), f"{slug}.md")
    if not os.path.exists(src):
        return False
    graveyard = os.path.join(partition_dir(partition), ".superseded")
    os.makedirs(graveyard, exist_ok=True)
    os.rename(src, os.path.join(graveyard, f"{slug}.{stamp}.md"))
    return True


def title_from_slug(slug):
    return " ".join(w.capitalize() for w in re.split(r"[-_]", slug))


def regen_memory_index(partition):
    """Rebuild MEMORY.md deterministically from fact frontmatter, so the index
    can never drift from the files on disk."""
    facts = read_partition(partition)
    lines = [f"- [{title_from_slug(f['slug'])}]({f['slug']}.md) — {f['description']}"
             for f in sorted(facts, key=lambda x: x["slug"])]
    with open(os.path.join(partition_dir(partition), "MEMORY.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + ("\n" if lines else ""))


# --- git ------------------------------------------------------------------
def git(*args, check=False):
    return subprocess.run(["git", "-C", MEM_HOME, *args],
                          capture_output=True, text=True, check=check)


def git_pull():
    if os.path.isdir(os.path.join(MEM_HOME, ".git")):
        git("pull", "--ff-only")


def commit_partition(partition, message, extra_paths=(), push=True):
    """Stage + commit ONLY this partition (+ any extra paths), never `git add -A`,
    so unrelated uncommitted memories are never swept in. Returns True if committed."""
    paths = [partition, *extra_paths]
    git("add", "--", *paths)
    st = git("status", "--porcelain", "--", partition).stdout.strip()
    if not st:
        return False
    git("commit", "-q", "-m", message, "--", *paths)
    if push:
        git("push")
    return True

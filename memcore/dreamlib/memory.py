"""dreamlib.memory — a MemoryDir: any directory of atomic markdown fact files
plus a MEMORY.md index. Dreams reads it as the "current memory" and writes edits
back into it. A mymemories partition is just one MemoryDir; so is any plain
folder you point --target at. Optionally git-commits if the dir is in a repo.
"""
import os, re, glob, subprocess

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
SKIP = {"MEMORY.md", "REGISTRY.md", "README.md", "index.md"}


def safe_slug(s):
    return bool(s) and bool(SLUG_RE.match(s)) and "/" not in s and ".." not in s


def _parse_frontmatter(text):
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    fm = {}
    for line in text[3:end].strip("\n").split("\n"):
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if m:
            fm[m.group(1)] = m.group(2).strip().strip('"')
    return fm, text[end + 4:].lstrip("\n")


def _title(slug):
    return " ".join(w.capitalize() for w in re.split(r"[-_]", slug))


class MemoryDir:
    def __init__(self, path):
        self.path = os.path.abspath(os.path.expanduser(path))

    def ensure(self):
        os.makedirs(self.path, exist_ok=True)

    def facts(self):
        out = []
        for p in sorted(glob.glob(os.path.join(self.path, "*.md"))):
            if os.path.basename(p) in SKIP:
                continue
            fm, body = _parse_frontmatter(open(p, encoding="utf-8").read())
            out.append({"slug": fm.get("name", os.path.splitext(os.path.basename(p))[0]),
                        "type": fm.get("type", "reference"),
                        "description": fm.get("description", ""),
                        "content": body.strip(), "path": p})
        return out

    def slugs(self):
        return {f["slug"] for f in self.facts()}

    def write_fact(self, slug, ftype, description, content, evidence, origin="dream"):
        self.ensure()
        fm = (f"---\nname: {slug}\n"
              f"description: \"{description.replace(chr(34), chr(39))}\"\n"
              f"metadata:\n  type: {ftype}\n  origin: {origin}\n"
              f"  evidence: {evidence}\n---\n\n{content.strip()}\n")
        p = os.path.join(self.path, f"{slug}.md")
        open(p, "w", encoding="utf-8").write(fm)
        return p

    def soft_delete(self, slug, stamp):
        src = os.path.join(self.path, f"{slug}.md")
        if not os.path.exists(src):
            return False
        grave = os.path.join(self.path, ".superseded")
        os.makedirs(grave, exist_ok=True)
        os.rename(src, os.path.join(grave, f"{slug}.{stamp}.md"))
        return True

    def regen_index(self):
        lines = [f"- [{_title(f['slug'])}]({f['slug']}.md) — {f['description']}"
                 for f in sorted(self.facts(), key=lambda x: x["slug"])]
        open(os.path.join(self.path, "MEMORY.md"), "w", encoding="utf-8").write(
            "\n".join(lines) + ("\n" if lines else ""))

    # --- optional git ----------------------------------------------------
    def _git_root(self):
        r = subprocess.run(["git", "-C", self.path, "rev-parse", "--show-toplevel"],
                           capture_output=True, text=True)
        return r.stdout.strip() if r.returncode == 0 else None

    def commit(self, message, push=False):
        root = self._git_root()
        if not root:
            return False
        rel = os.path.relpath(self.path, root)
        subprocess.run(["git", "-C", root, "add", "--", rel], capture_output=True, text=True)
        st = subprocess.run(["git", "-C", root, "status", "--porcelain", "--", rel],
                            capture_output=True, text=True).stdout.strip()
        if not st:
            return False
        subprocess.run(["git", "-C", root, "commit", "-q", "-m", message, "--", rel],
                       capture_output=True, text=True)
        if push:
            subprocess.run(["git", "-C", root, "push"], capture_output=True, text=True)
        return True

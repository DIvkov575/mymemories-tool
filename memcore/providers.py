"""memcore.providers — mymemories provider adapters.

The reflection engine + headless-LLM/transcript backends now live in the
vendored, single-source `dreamlib` (shared with the standalone `dreams` tool).
This module keeps ONLY the mymemories-specific concerns on top of a dreamlib
backend: turning a project into a partition's transcripts, and exposing a
partition so a harness auto-loads it (Claude symlink / Codex AGENTS.md pointer).

No headless-LLM or transcript-extraction logic is duplicated here — it delegates
to dreamlib.providers.{ClaudeBackend,CodexBackend}.
"""
import os, glob
from . import store
from .dreamlib import providers as dp

HOME = store.HOME
CORPUS_CHARS = int(os.environ.get("DREAM_CORPUS_CHARS", "80000"))


class Provider:
    name = "base"

    def __init__(self):
        self.backend = None  # a dreamlib Backend

    def available(self):
        return self.backend.available()

    def run_llm(self, prompt, model=None, timeout=600):
        return self.backend.run_llm(prompt, model=model, timeout=timeout)

    def transcripts(self, project_abs, since_ts):
        raise NotImplementedError

    def link(self, partition, project_abs):
        raise NotImplementedError

    def _assemble(self, files_newest_first, since_ts):
        chunks, sids, total = [], [], 0
        for p, sid in files_newest_first:
            if since_ts and os.path.getmtime(p) <= since_ts:
                continue
            text = self.backend.extract(p)
            if not text.strip():
                continue
            piece = f"\n===== SESSION {sid} =====\n{text}"
            if total + len(piece) > CORPUS_CHARS:
                piece = piece[: max(0, CORPUS_CHARS - total)]
            chunks.append(piece); sids.append(sid); total += len(piece)
            if total >= CORPUS_CHARS:
                break
        return "".join(chunks), sids


class ClaudeProvider(Provider):
    name = "claude"

    def __init__(self):
        self.backend = dp.ClaudeBackend()
        self.home = self.backend.home

    def _projects_dir(self, project_abs):
        return os.path.join(self.home, "projects", store.mangle(project_abs))

    def transcripts(self, project_abs, since_ts):
        files = sorted(glob.glob(os.path.join(self._projects_dir(project_abs), "*.jsonl")),
                       key=os.path.getmtime, reverse=True)
        pairs = [(p, os.path.splitext(os.path.basename(p))[0]) for p in files]
        return self._assemble(pairs, since_ts)

    def link(self, partition, project_abs):
        link = os.path.join(self._projects_dir(project_abs), "memory")
        target = store.partition_dir(partition)
        os.makedirs(os.path.dirname(link), exist_ok=True)
        if os.path.islink(link):
            os.remove(link)
        elif os.path.exists(link):
            os.rename(link, link + ".pre-mymemories.bak")
        os.symlink(target, link)
        return link


class CodexProvider(Provider):
    name = "codex"

    def __init__(self):
        self.backend = dp.CodexBackend()
        self.home = self.backend.home

    def transcripts(self, project_abs, since_ts):
        files = sorted(glob.glob(os.path.join(self.home, "sessions", "**", "rollout-*.jsonl"),
                                 recursive=True), key=os.path.getmtime, reverse=True)
        pairs = []
        for p in files:
            cwd, sid = self._meta(p)
            if cwd and os.path.realpath(cwd) == os.path.realpath(project_abs):
                pairs.append((p, sid or os.path.basename(p)))
        return self._assemble(pairs, since_ts)

    @staticmethod
    def _meta(path):
        import json
        try:
            with open(path, encoding="utf-8") as f:
                obj = json.loads(f.readline())
            if obj.get("type") == "session_meta":
                pl = obj.get("payload") or {}
                return pl.get("cwd"), pl.get("session_id") or pl.get("id")
        except (OSError, ValueError):
            pass
        return None, None

    def link(self, partition, project_abs):
        # Expose the partition to Codex via a pointer + memorize/sync reminder in
        # the project's AGENTS.md. Refreshes an existing (possibly older) block in
        # place, bounded by markers. Skips cleanly if the project dir is absent.
        if not os.path.isdir(project_abs):
            return None
        agents = os.path.join(project_abs, "AGENTS.md")
        target = store.partition_dir(partition)
        marker, end_marker = "<!-- mymemories -->", "<!-- /mymemories -->"
        block = (
            f"{marker}\n## Project memory\n"
            f"Persistent memory for this project lives at `{target}`.\n"
            f"**On session start**, sync it: "
            f"`git -C {store.MEM_HOME} pull --ff-only` (best-effort), then read "
            f"`{target}/MEMORY.md` for the index; load individual facts on demand.\n\n"
            f"When a durable, reusable fact emerges (a user preference or correction, "
            f"a hard-won decision, a non-obvious constraint), save + sync it:\n"
            f"`python3 ~/workplace/mymemories-tool/mymem --provider codex save <slug> "
            f"--type feedback --description \"<hook>\" --content \"<fact>\"`\n"
            f"Be selective — do not save task status or restated context.\n"
            f"{end_marker}\n")
        existing = open(agents, encoding="utf-8").read() if os.path.exists(agents) else ""
        if marker in existing:
            import re as _re
            if end_marker in existing:
                new_text = _re.sub(_re.escape(marker) + r".*?" + _re.escape(end_marker) + r"\n?",
                                   block, existing, flags=_re.S)
            else:
                new_text = existing[:existing.index(marker)] + block
            if new_text != existing:
                open(agents, "w", encoding="utf-8").write(new_text)
            return agents
        with open(agents, "a", encoding="utf-8") as f:
            if existing and not existing.endswith("\n"):
                f.write("\n")
            f.write(("\n" if existing else "") + block)
        return agents


PROVIDERS = {"claude": ClaudeProvider, "codex": CodexProvider}


def get_provider(name=None):
    name = name or os.environ.get("MYMEM_PROVIDER")
    if name:
        if name not in PROVIDERS:
            raise SystemExit(f"unknown provider {name!r}; choices: {', '.join(PROVIDERS)}")
        return PROVIDERS[name]()
    for cls in (ClaudeProvider, CodexProvider):
        p = cls()
        if p.available():
            return p
    return ClaudeProvider()

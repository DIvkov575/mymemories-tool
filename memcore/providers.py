"""memcore.providers — the ONLY harness-specific code.

A Provider abstracts the three things that differ between coding agents:
  1. transcripts(project_abs, since_ts) -> (corpus_text, [session_ids])
       where a project's conversation logs live and how to read them.
  2. run_llm(prompt) -> str
       how to invoke the agent's own model headlessly (reuses its auth).
  3. link(partition, project_abs) -> str
       how to expose a partition so the harness auto-loads it for that project.

Everything else (the store, the dreaming algorithm, the guards) is neutral and
lives in memcore.store / memcore.dream. Add a new agent = add a Provider here.
"""
import os, json, glob, subprocess, shutil
from . import store

HOME = store.HOME


class Provider:
    name = "base"
    #: chars of transcript to feed the consolidator per partition
    corpus_chars = 80000

    def available(self):
        """True if this provider's CLI/dirs exist on this machine."""
        return False

    # --- 1. transcripts ---------------------------------------------------
    def transcripts(self, project_abs, since_ts):
        raise NotImplementedError

    # --- 2. headless LLM --------------------------------------------------
    def run_llm(self, prompt, model=None, timeout=600):
        raise NotImplementedError

    # --- 3. memory exposure ----------------------------------------------
    def link(self, partition, project_abs):
        raise NotImplementedError

    # --- shared helper: assemble a capped, newest-first corpus ------------
    def _assemble(self, files_newest_first, since_ts, extract):
        chunks, sids, total = [], [], 0
        for p, sid in files_newest_first:
            if since_ts and os.path.getmtime(p) <= since_ts:
                continue
            text = extract(p)
            if not text.strip():
                continue
            piece = f"\n===== SESSION {sid} =====\n" + text
            if total + len(piece) > self.corpus_chars:
                piece = piece[: max(0, self.corpus_chars - total)]
            chunks.append(piece); sids.append(sid); total += len(piece)
            if total >= self.corpus_chars:
                break
        return "".join(chunks), sids


# ---------------------------------------------------------------------------
class ClaudeProvider(Provider):
    name = "claude"

    def __init__(self):
        self.home = os.environ.get("CLAUDE_HOME", os.path.join(HOME, ".claude"))

    def available(self):
        return shutil.which("claude") is not None or os.path.isdir(os.path.join(self.home, "projects"))

    def _projects_dir(self, project_abs):
        return os.path.join(self.home, "projects", store.mangle(project_abs))

    def transcripts(self, project_abs, since_ts):
        tdir = self._projects_dir(project_abs)
        files = sorted(glob.glob(os.path.join(tdir, "*.jsonl")),
                       key=os.path.getmtime, reverse=True)
        pairs = [(p, os.path.splitext(os.path.basename(p))[0]) for p in files]
        return self._assemble(pairs, since_ts, self._extract)

    @staticmethod
    def _extract(path):
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
                                out.append(f"{role.upper()}: {b.get('text','')}")
        except OSError:
            return ""
        return "\n".join(out)

    def run_llm(self, prompt, model=None, timeout=600):
        model = model or os.environ.get("DREAM_MODEL", "sonnet")
        proc = subprocess.run(
            ["claude", "-p", prompt, "--output-format", "json", "--model", model],
            capture_output=True, text=True, timeout=timeout,
            env={**os.environ, "CLAUDE_HOME": self.home},
        )
        if proc.returncode != 0:
            raise RuntimeError(f"claude -p exit {proc.returncode}: {proc.stderr[:200]}")
        raw = proc.stdout
        try:
            env = json.loads(raw)
            return env.get("result", raw) if isinstance(env, dict) else raw
        except ValueError:
            return raw

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


# ---------------------------------------------------------------------------
class CodexProvider(Provider):
    name = "codex"

    def __init__(self):
        self.home = os.environ.get("CODEX_HOME", os.path.join(HOME, ".codex"))

    def available(self):
        return shutil.which("codex") is not None or os.path.isdir(os.path.join(self.home, "sessions"))

    def transcripts(self, project_abs, since_ts):
        # Codex logs are ~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl; each file's
        # session_meta carries the cwd, so filter to this project.
        sdir = os.path.join(self.home, "sessions")
        files = sorted(glob.glob(os.path.join(sdir, "**", "rollout-*.jsonl"), recursive=True),
                       key=os.path.getmtime, reverse=True)
        pairs = []
        for p in files:
            cwd, sid = self._meta(p)
            if cwd and os.path.realpath(cwd) == os.path.realpath(project_abs):
                pairs.append((p, sid or os.path.basename(p)))
        return self._assemble(pairs, since_ts, self._extract)

    @staticmethod
    def _meta(path):
        """Read cwd + session_id from the first session_meta line."""
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    try:
                        obj = json.loads(line)
                    except ValueError:
                        continue
                    if obj.get("type") == "session_meta":
                        pl = obj.get("payload") or {}
                        return pl.get("cwd"), pl.get("session_id") or pl.get("id")
                    break  # meta is the first line; stop if it isn't
        except OSError:
            pass
        return None, None

    #: roles that are harness boilerplate, not conversation
    _SKIP_ROLES = {"developer", "system", "tool"}

    @classmethod
    def _extract(cls, path):
        """Pull genuine user/assistant conversation text from a rollout jsonl,
        skipping developer/system boilerplate and non-message events."""
        out = []
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    try:
                        obj = json.loads(line)
                    except ValueError:
                        continue
                    t = obj.get("type")
                    pl = obj.get("payload") or {}
                    if t == "response_item" and pl.get("type") == "message":
                        role = pl.get("role")
                        if role in cls._SKIP_ROLES:
                            continue
                        text = cls._content_text(pl.get("content"))
                        if text.strip() and not cls._is_wrapper(text):
                            out.append(f"{(role or 'user').upper()}: {text.strip()}")
                    elif t == "event_msg" and pl.get("type") in ("agent_message", "user_message"):
                        text = pl.get("message") or ""
                        if isinstance(text, str) and text.strip():
                            role = "ASSISTANT" if pl["type"] == "agent_message" else "USER"
                            out.append(f"{role}: {text.strip()}")
        except OSError:
            return ""
        return "\n".join(out)

    @staticmethod
    def _content_text(content):
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return " ".join(
                b.get("text", "") for b in content
                if isinstance(b, dict) and b.get("type") in ("text", "input_text", "output_text")
            )
        return ""

    @staticmethod
    def _is_wrapper(text):
        """True for Codex-injected context wrappers (not real conversation)."""
        s = text.lstrip()
        return s.startswith("<environment_context>") or s.startswith("<permissions") \
            or s.startswith("<user_instructions>")

    def run_llm(self, prompt, model=None, timeout=600):
        # codex exec runs non-interactively and prints the model's final text.
        cmd = ["codex", "exec", "--skip-git-repo-check", prompt]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                              env={**os.environ})
        if proc.returncode != 0:
            raise RuntimeError(f"codex exec exit {proc.returncode}: {proc.stderr[:200]}")
        return proc.stdout

    def link(self, partition, project_abs):
        # Codex has no per-project symlinked memory dir; instead drop a pointer
        # into the project's AGENTS.md so the agent reads the partition on load.
        agents = os.path.join(project_abs, "AGENTS.md")
        target = store.partition_dir(partition)
        marker = "<!-- mymemories -->"
        block = (f"{marker}\n## Project memory\n"
                 f"Persistent memory for this project lives at `{target}`. "
                 f"Read `{target}/MEMORY.md` for the index; load individual facts on demand.\n")
        existing = ""
        if os.path.exists(agents):
            existing = open(agents, encoding="utf-8").read()
            if marker in existing:
                return agents  # already pointed
        with open(agents, "a", encoding="utf-8") as f:
            if existing and not existing.endswith("\n"):
                f.write("\n")
            f.write("\n" + block)
        return agents


PROVIDERS = {"claude": ClaudeProvider, "codex": CodexProvider}


def get_provider(name=None):
    """Resolve a provider by name, or auto-detect. Priority: explicit arg >
    MYMEM_PROVIDER env > first available > claude."""
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

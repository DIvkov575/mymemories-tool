"""dreamlib.providers — headless LLM backends + session-transcript sources.

A backend does two things: run a model headlessly (reusing the agent's own
auth) and locate/read session transcripts. Dreams is otherwise agent-agnostic.
"""
import os, glob, json, subprocess, shutil

HOME = os.path.expanduser("~")


class Backend:
    name = "base"

    def available(self):
        return False

    def run_llm(self, prompt, model=None, timeout=600):
        raise NotImplementedError

    def sessions(self):
        """Return [(path, session_id, mtime)] newest first."""
        return []

    def latest_session(self):
        s = self.sessions()
        return s[0] if s else None

    def find_session(self, ident):
        """Resolve a session by id substring or file path."""
        if os.path.isfile(ident):
            return (ident, os.path.splitext(os.path.basename(ident))[0], os.path.getmtime(ident))
        for path, sid, mt in self.sessions():
            if ident in sid or ident in os.path.basename(path):
                return (path, sid, mt)
        return None

    def extract(self, path):
        """Transcript path -> plain conversation text."""
        raise NotImplementedError


class ClaudeBackend(Backend):
    name = "claude"

    def __init__(self):
        self.home = os.environ.get("CLAUDE_HOME", os.path.join(HOME, ".claude"))

    def available(self):
        return shutil.which("claude") is not None or os.path.isdir(os.path.join(self.home, "projects"))

    def run_llm(self, prompt, model=None, timeout=600):
        model = model or os.environ.get("DREAM_MODEL", "sonnet")
        proc = subprocess.run(
            ["claude", "-p", prompt, "--output-format", "json", "--model", model],
            capture_output=True, text=True, timeout=timeout,
            env={**os.environ, "CLAUDE_HOME": self.home})
        if proc.returncode != 0:
            raise RuntimeError(f"claude -p exit {proc.returncode}: {proc.stderr[:200]}")
        try:
            env = json.loads(proc.stdout)
            return env.get("result", proc.stdout) if isinstance(env, dict) else proc.stdout
        except ValueError:
            return proc.stdout

    def sessions(self):
        out = []
        for p in glob.glob(os.path.join(self.home, "projects", "*", "*.jsonl")):
            out.append((p, os.path.splitext(os.path.basename(p))[0], os.path.getmtime(p)))
        return sorted(out, key=lambda x: x[2], reverse=True)

    def extract(self, path):
        lines = []
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
                        lines.append(f"{role.upper()}: {c}")
                    elif isinstance(c, list):
                        for b in c:
                            if isinstance(b, dict) and b.get("type") == "text":
                                lines.append(f"{role.upper()}: {b.get('text','')}")
        except OSError:
            return ""
        return "\n".join(lines)


class CodexBackend(Backend):
    name = "codex"
    _SKIP_ROLES = {"developer", "system", "tool"}

    def __init__(self):
        self.home = os.environ.get("CODEX_HOME", os.path.join(HOME, ".codex"))

    def available(self):
        return shutil.which("codex") is not None or os.path.isdir(os.path.join(self.home, "sessions"))

    def run_llm(self, prompt, model=None, timeout=600):
        proc = subprocess.run(["codex", "exec", "--skip-git-repo-check", prompt],
                              capture_output=True, text=True, timeout=timeout, env={**os.environ})
        if proc.returncode != 0:
            raise RuntimeError(f"codex exec exit {proc.returncode}: {proc.stderr[:200]}")
        return proc.stdout

    def sessions(self):
        out = []
        for p in glob.glob(os.path.join(self.home, "sessions", "**", "rollout-*.jsonl"), recursive=True):
            out.append((p, self._sid(p), os.path.getmtime(p)))
        return sorted(out, key=lambda x: x[2], reverse=True)

    @staticmethod
    def _sid(path):
        try:
            obj = json.loads(open(path, encoding="utf-8").readline())
            if obj.get("type") == "session_meta":
                pl = obj.get("payload") or {}
                return pl.get("session_id") or pl.get("id") or os.path.basename(path)
        except (OSError, ValueError):
            pass
        return os.path.basename(path)

    @classmethod
    def extract(cls, path):
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
            return " ".join(b.get("text", "") for b in content
                            if isinstance(b, dict) and b.get("type") in ("text", "input_text", "output_text"))
        return ""

    @staticmethod
    def _is_wrapper(text):
        s = text.lstrip()
        return s.startswith(("<environment_context>", "<permissions", "<user_instructions>"))


BACKENDS = {"claude": ClaudeBackend, "codex": CodexBackend}


def get_backend(name=None):
    name = name or os.environ.get("DREAM_BACKEND")
    if name:
        if name not in BACKENDS:
            raise SystemExit(f"unknown backend {name!r}; choices: {', '.join(BACKENDS)}")
        return BACKENDS[name]()
    for cls in (ClaudeBackend, CodexBackend):
        b = cls()
        if b.available():
            return b
    return ClaudeBackend()

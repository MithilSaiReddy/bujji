"""
bujji/identity.py
Identity layer — loads the four core Markdown files that define who bujji is
and who it's talking to. Files live in workspace/ and are loaded in priority order:

    SOUL.md      Values, principles, refusals. The ethical core. You write this.
    IDENTITY.md  Name, personality, tone, quirks. You write this.
    USER.md      Who the user is — projects, prefs, context. Agent updates this.
    AGENT.md     What tools/skills are active. Agent can update this.

Philosophy: plain Markdown, human-readable, editable in any text editor.
No JSON schemas. No embeddings. Just files.

To customise bujji: open any of these files and edit them freely.
To reset: delete the file — a fresh default will be created on next run.
"""

from pathlib import Path

# ── File names (all live directly in workspace/) ──────────────────────────────
SOUL_FILE     = "SOUL.md"
IDENTITY_FILE = "IDENTITY.md"
USER_FILE     = "USER.md"
AGENT_FILE    = "AGENT.md"

# ── Default content ───────────────────────────────────────────────────────────
# Written on first run if the file doesn't exist.
# Users should edit these to personalise their bujji.

_DEFAULT_SOUL = """\
# Soul

- Be helpful, honest, and concise.
- Prefer action over lengthy explanation.
- Never fabricate facts — say "I don't know" rather than guess.
- Respect the user's privacy and autonomy.
- Always complete the task before summarising.
- When something is worth remembering, update USER.md without being asked.
"""

_DEFAULT_IDENTITY = """\
# Identity

You are **bujji** — an ultra-lightweight personal AI assistant.
You are efficient, direct, and a little warm. You don't ramble.
You are inspired by the loyal robot companion from *Kalki 2898 AD*.

Your tone: concise, capable, occasionally dry. No filler phrases.
"""

_DEFAULT_USER = """\
# User

_This file is updated by bujji as it learns about you._
_You can also edit it directly._

No information stored yet.
"""

_DEFAULT_AGENT = """\
# Agent Capabilities

- **Web search** via Brave Search API
- **File operations**: read, write, list, delete
- **Shell execution**: run any shell command
- **Utilities**: current time, send messages
- **Memory**: update USER.md to remember things across sessions

_This file is updated automatically when skills or tools change._
"""

_DEFAULTS = {
    SOUL_FILE:     _DEFAULT_SOUL,
    IDENTITY_FILE: _DEFAULT_IDENTITY,
    USER_FILE:     _DEFAULT_USER,
    AGENT_FILE:    _DEFAULT_AGENT,
}


# ── Public API ────────────────────────────────────────────────────────────────

def ensure_identity_files(workspace: Path) -> None:
    """
    Create any missing identity files with sensible defaults.
    Call once at agent startup.
    """
    workspace.mkdir(parents=True, exist_ok=True)
    for filename, default_content in _DEFAULTS.items():
        path = workspace / filename
        if not path.exists():
            path.write_text(default_content, encoding="utf-8")


def load_identity_block(workspace: Path) -> str:
    """
    Read all four identity files and return a single string to inject
    at the top of the system prompt (before skills).

    Missing files are silently skipped (ensure_identity_files should
    have been called first, but this is defensive).
    """
    sections = []
    for filename in [SOUL_FILE, IDENTITY_FILE, USER_FILE, AGENT_FILE]:
        path = workspace / filename
        if path.exists():
            try:
                content = path.read_text(encoding="utf-8", errors="replace").strip()
                if content:
                    sections.append(content)
            except Exception:
                pass
    return "\n\n---\n\n".join(sections)


def update_user_file(workspace: Path, new_content: str) -> str:
    """
    Overwrite USER.md with new_content.
    Called by the update_user_memory tool.
    Returns a confirmation string.
    """
    path = workspace / USER_FILE
    path.write_text(new_content, encoding="utf-8")
    return f"USER.md updated ({len(new_content)} chars)"


def read_user_file(workspace: Path) -> str:
    """Return the current contents of USER.md."""
    path = workspace / USER_FILE
    if not path.exists():
        return "(USER.md not found)"
    return path.read_text(encoding="utf-8", errors="replace")

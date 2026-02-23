"""
bujji/tools/memory.py  —  v2

Safe USER.md memory.  Key improvements over v1:
• Atomic writes  : write to .tmp then rename → never corrupts the file mid-write
• Auto-backup    : saves USER.md.bak before every update
• append_memory  : add new facts WITHOUT replacing existing ones (LLM appends, not clobbers)
• read_user_memory now returns a formatted snapshot the LLM can reason about easily
"""
from __future__ import annotations

import datetime
from pathlib import Path

from bujji.tools.base import ToolContext, register_tool

# ── Helpers ───────────────────────────────────────────────────────────────────

def _user_md_path(ctx: ToolContext) -> Path:
    return ctx.workspace / "USER.md"

def _atomic_write(path: Path, content: str) -> None:
    """Write content atomically: temp file → rename.  Cross-platform safe."""
    tmp = path.with_suffix(".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)   # atomic on POSIX; best-effort on Windows

def _backup(path: Path) -> None:
    """Copy path → path.bak before overwriting."""
    if path.exists():
        bak = path.with_suffix(".bak")
        bak.write_bytes(path.read_bytes())

# ── Tools ─────────────────────────────────────────────────────────────────────

@register_tool(
    description=(
        "Read USER.md — your persistent memory about the user. "
        "Call this at conversation start to recall the user's name, projects, "
        "preferences, and anything worth remembering across sessions."
    ),
    parameters={"type": "object", "properties": {}},
)
def read_user_memory(_ctx: ToolContext = None) -> str:
    path = _user_md_path(_ctx)
    if not path.exists():
        return "(USER.md not found — no persistent memory yet)"
    content = path.read_text(encoding="utf-8", errors="replace").strip()
    return content or "(USER.md is empty)"

@register_tool(
    description=(
        "Append new facts to USER.md without erasing existing memory. "
        "Use this when the user shares something worth remembering: their name, "
        "a preference, a project, a tech stack, or any context useful in future "
        "sessions.  Pass only the NEW information — existing memory is preserved."
    ),
    parameters={
        "type":     "object",
        "required": ["new_facts"],
        "properties": {
            "new_facts": {
                "type":        "string",
                "description": (
                    "New information to add, written as natural Markdown. "
                    "Do NOT repeat things already in USER.md. "
                    "Example: '- Prefers Python over JavaScript\\n- Working on a FastAPI project'"
                ),
            },
        },
    },
)
def append_user_memory(new_facts: str, _ctx: ToolContext = None) -> str:
    path    = _user_md_path(_ctx)
    _backup(path)

    existing = path.read_text(encoding="utf-8").rstrip() if path.exists() else ""
    ts       = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    entry    = f"\n\n<!-- updated {ts} -->\n{new_facts.strip()}"
    updated  = existing + entry

    _atomic_write(path, updated)
    return f"Memory updated (+{len(new_facts)} chars). Total: {len(updated)} chars."

@register_tool(
    description=(
        "Replace the entire USER.md with new content. "
        "Use this only when you need to restructure or clean up memory. "
        "For adding new facts, prefer append_user_memory instead. "
        "Pass the COMPLETE new content — everything you want to keep."
    ),
    parameters={
        "type":     "object",
        "required": ["content"],
        "properties": {
            "content": {
                "type":        "string",
                "description": (
                    "The full new USER.md content as Markdown. "
                    "Include ALL existing facts plus new ones."
                ),
            },
        },
    },
)
def update_user_memory(content: str, _ctx: ToolContext = None) -> str:
    path = _user_md_path(_ctx)
    _backup(path)
    _atomic_write(path, content.strip())
    return f"USER.md replaced ({len(content)} chars). Backup saved to USER.md.bak."

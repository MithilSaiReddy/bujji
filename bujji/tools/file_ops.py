"""
bujji/tools/file_ops.py  —  v2
File operations: read, write (atomic), append, list, delete.

Changes vs v1:
• Atomic writes via .tmp → rename (never partial writes)
• append_file tool added (no need to read-modify-write for logs/journals)
• list_files shows sizes and a summary line
• _safe_path moved here as a proper helper
"""
from __future__ import annotations

import shutil
from pathlib import Path

from bujji.tools.base import ToolContext, register_tool

# ── Path helper ───────────────────────────────────────────────────────────────

def _safe_path(path_str: str, ctx: ToolContext) -> Path:
    """
    Resolve a path string:
    • Relative paths are anchored to workspace.
    • If restrict=True, absolute paths outside workspace are blocked.
    """
    p = Path(path_str).expanduser()
    if not p.is_absolute():
        p = ctx.workspace / p

    if ctx.restrict:
        try:
            p.resolve().relative_to(ctx.workspace.resolve())
        except ValueError:
            raise ValueError(
                f"Path '{path_str}' is outside the workspace '{ctx.workspace}'. "
                "Disable restrict_to_workspace in config to allow absolute paths."
            )
    return p

def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)

# ── Tools ─────────────────────────────────────────────────────────────────────

@register_tool(
    description="Read the full text content of a file from disk.",
    parameters={
        "type":     "object",
        "required": ["path"],
        "properties": {
            "path": {
                "type":        "string",
                "description": "File path — relative to workspace or absolute.",
            },
        },
    },
)
def read_file(path: str, _ctx: ToolContext = None) -> str:
    try:
        p = _safe_path(path, _ctx)
    except ValueError as e:
        return f"[TOOL ERROR] {e}"

    if not p.exists():
        return f"[NOT FOUND] {p}"
    if p.is_dir():
        return f"[ERROR] '{p}' is a directory — use list_files to inspect it."
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
        return text if text else "(file is empty)"
    except Exception as e:
        return f"[READ ERROR] {e}"

@register_tool(
    description=(
        "Write (or overwrite) a file with the given text content. "
        "The write is atomic — no partial files on crash."
    ),
    parameters={
        "type":     "object",
        "required": ["path", "content"],
        "properties": {
            "path":    {"type": "string", "description": "Destination file path."},
            "content": {"type": "string", "description": "Full text content to write."},
        },
    },
)
def write_file(path: str, content: str, _ctx: ToolContext = None) -> str:
    try:
        p = _safe_path(path, _ctx)
    except ValueError as e:
        return f"[TOOL ERROR] {e}"
    try:
        _atomic_write(p, content)
        return f"Written {len(content):,} chars to {p}"
    except Exception as e:
        return f"[WRITE ERROR] {e}"

@register_tool(
    description=(
        "Append text to the end of a file (creates the file if it doesn't exist). "
        "Ideal for logs, journals, and incremental notes."
    ),
    parameters={
        "type":     "object",
        "required": ["path", "content"],
        "properties": {
            "path":    {"type": "string", "description": "File path to append to."},
            "content": {"type": "string", "description": "Text to add at the end."},
        },
    },
)
def append_file(path: str, content: str, _ctx: ToolContext = None) -> str:
    try:
        p = _safe_path(path, _ctx)
    except ValueError as e:
        return f"[TOOL ERROR] {e}"
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            f.write(content)
        return f"Appended {len(content):,} chars to {p} (total: {p.stat().st_size:,} bytes)"
    except Exception as e:
        return f"[APPEND ERROR] {e}"

@register_tool(
    description="List files and subdirectories inside a directory with sizes.",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type":        "string",
                "description": "Directory to list (default: workspace root).",
            },
        },
    },
)
def list_files(path: str = ".", _ctx: ToolContext = None) -> str:
    try:
        p = _safe_path(path, _ctx)
    except ValueError as e:
        return f"[TOOL ERROR] {e}"

    if not p.exists():
        return f"[NOT FOUND] {p}"
    if p.is_file():
        sz = p.stat().st_size
        return f"(file) {p}  [{sz:,} bytes]"

    try:
        items = sorted(p.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
    except PermissionError:
        return f"[PERMISSION ERROR] Cannot read {p}"

    if not items:
        return f"{p}: (empty directory)"

    lines = []
    for item in items:
        if item.is_dir():
            lines.append(f"📁  {item.name}/")
        else:
            sz = item.stat().st_size
            lines.append(f"📄  {item.name}  [{sz:,} bytes]")

    summary = f"\n\n{len([i for i in items if i.is_dir()])} dirs, " \
              f"{len([i for i in items if i.is_file()])} files"
    return f"Contents of {p}:\n" + "\n".join(lines) + summary

@register_tool(
    description="Delete a file or entire directory tree.",
    parameters={
        "type":     "object",
        "required": ["path"],
        "properties": {
            "path": {"type": "string", "description": "Path to delete."},
        },
    },
)
def delete_file(path: str, _ctx: ToolContext = None) -> str:
    try:
        p = _safe_path(path, _ctx)
    except ValueError as e:
        return f"[TOOL ERROR] {e}"

    if not p.exists():
        return f"[NOT FOUND] {p}"
    try:
        if p.is_dir():
            shutil.rmtree(p)
            return f"Deleted directory (recursive): {p}"
        p.unlink()
        return f"Deleted file: {p}"
    except Exception as e:
        return f"[DELETE ERROR] {e}"

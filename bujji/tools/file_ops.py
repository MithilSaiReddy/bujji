"""
bujji/tools/file_ops.py
File operation tools: read_file, write_file, list_files, delete_file.
Each function accepts _ctx injected by ToolRegistry at call time.
"""

import shutil
from pathlib import Path

from bujji.tools.base import register_tool


def _safe_path(path: str, ctx: dict) -> Path:
    """
    Resolve a path.  If relative, anchor it inside the workspace.
    If restrict_to_workspace is True, raise on any escape attempt.
    """
    workspace = ctx["workspace"]
    restrict  = ctx["restrict"]

    p = Path(path).expanduser()
    if not p.is_absolute():
        p = workspace / p

    if restrict:
        try:
            p.resolve().relative_to(workspace.resolve())
        except ValueError:
            raise ValueError(f"Path is outside the workspace: {p}")

    return p


# ─────────────────────────────────────────────────────────────────────────────

@register_tool(
    description="Read the full contents of a file from disk.",
    parameters={
        "type": "object",
        "required": ["path"],
        "properties": {
            "path": {
                "type":        "string",
                "description": "File path — relative to workspace or absolute.",
            }
        },
    },
)
def read_file(path: str, _ctx: dict = None) -> str:
    p = _safe_path(path, _ctx)
    if not p.exists():
        return f"File not found: {p}"
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"Read error: {e}"


@register_tool(
    description="Write (or overwrite) a file on disk with the given content.",
    parameters={
        "type": "object",
        "required": ["path", "content"],
        "properties": {
            "path":    {"type": "string", "description": "Destination file path."},
            "content": {"type": "string", "description": "Text content to write."},
        },
    },
)
def write_file(path: str, content: str, _ctx: dict = None) -> str:
    p = _safe_path(path, _ctx)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return f"Written {len(content)} bytes to {p}"


@register_tool(
    description="List files and subdirectories inside a directory.",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type":        "string",
                "description": "Directory to list (default: workspace root).",
            }
        },
    },
)
def list_files(path: str = ".", _ctx: dict = None) -> str:
    p = _safe_path(path, _ctx)
    if not p.exists():
        return f"Path not found: {p}"
    if p.is_file():
        return f"(file) {p}"
    items = sorted(p.iterdir())
    if not items:
        return f"{p}: (empty directory)"
    lines = [
        f"{'[DIR]  ' if item.is_dir() else '[FILE] '}{item.name}"
        for item in items
    ]
    return f"Contents of {p}:\n" + "\n".join(lines)


@register_tool(
    description="Delete a file or directory (recursive).",
    parameters={
        "type": "object",
        "required": ["path"],
        "properties": {
            "path": {"type": "string", "description": "Path to delete."},
        },
    },
)
def delete_file(path: str, _ctx: dict = None) -> str:
    p = _safe_path(path, _ctx)
    if not p.exists():
        return f"Not found: {p}"
    if p.is_dir():
        shutil.rmtree(p)
        return f"Deleted directory: {p}"
    p.unlink()
    return f"Deleted file: {p}"
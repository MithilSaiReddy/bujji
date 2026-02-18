"""
bujji/tools/memory.py
Persistent memory tool — remember, recall, forget, list_memories.

Facts are stored in workspace/memory.json as plain human-readable JSON.
You can edit the file directly to correct or seed bujji's memory.

Philosophy: No database. No embeddings. Just a JSON file you can open in
any text editor. Fits perfectly on a Raspberry Pi.
"""

import json
from pathlib import Path

from bujji.tools.base import register_tool

# ── Internal helpers ──────────────────────────────────────────────────────────

def _memory_path(ctx: dict) -> Path:
    return ctx["workspace"] / "memory.json"


def _load(ctx: dict) -> dict:
    path = _memory_path(ctx)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(ctx: dict, data: dict) -> None:
    path = _memory_path(ctx)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# ── Tools ─────────────────────────────────────────────────────────────────────

@register_tool(
    description=(
        "Save a piece of information to persistent memory so you can recall it "
        "in future conversations. Use a short descriptive key and a value. "
        "Examples: key='user_name' value='Alice', key='preferred_language' value='Python'."
    ),
    parameters={
        "type": "object",
        "required": ["key", "value"],
        "properties": {
            "key": {
                "type":        "string",
                "description": "Short identifier for this memory (e.g. 'user_name', 'project_path').",
            },
            "value": {
                "type":        "string",
                "description": "The information to remember.",
            },
        },
    },
)
def remember(key: str, value: str, _ctx: dict = None) -> str:
    data = _load(_ctx)
    data[key] = value
    _save(_ctx, data)
    return f"Remembered: {key} = {value}"


@register_tool(
    description=(
        "Recall a specific piece of information from persistent memory by key."
    ),
    parameters={
        "type": "object",
        "required": ["key"],
        "properties": {
            "key": {
                "type":        "string",
                "description": "The memory key to look up.",
            },
        },
    },
)
def recall(key: str, _ctx: dict = None) -> str:
    data = _load(_ctx)
    if key not in data:
        return f"No memory found for key: '{key}'"
    return f"{key} = {data[key]}"


@register_tool(
    description="Delete a specific memory by key.",
    parameters={
        "type": "object",
        "required": ["key"],
        "properties": {
            "key": {
                "type":        "string",
                "description": "The memory key to delete.",
            },
        },
    },
)
def forget(key: str, _ctx: dict = None) -> str:
    data = _load(_ctx)
    if key not in data:
        return f"No memory found for key: '{key}'"
    del data[key]
    _save(_ctx, data)
    return f"Forgot: {key}"


@register_tool(
    description="List all keys and values currently stored in persistent memory.",
    parameters={"type": "object", "properties": {}},
)
def list_memories(_ctx: dict = None) -> str:
    data = _load(_ctx)
    if not data:
        return "Memory is empty."
    lines = [f"  {k}: {v}" for k, v in data.items()]
    return "Stored memories:\n" + "\n".join(lines)


# ── Public loader (called by agent.py to inject memory into system prompt) ────

def load_memory_summary(workspace: Path) -> str:
    """
    Returns a compact memory block for injection into the system prompt.
    Called once per AgentLoop init — zero overhead after that.
    """
    path = workspace / "memory.json"
    if not path.exists():
        return ""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not data:
            return ""
        lines = [f"  {k}: {v}" for k, v in data.items()]
        return "# What I Remember About You\n" + "\n".join(lines)
    except Exception:
        return ""

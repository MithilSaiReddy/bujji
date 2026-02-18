"""
bujji/tools/memory.py
Memory tools — read and update USER.md in the workspace.

Instead of a key-value store, bujji keeps a single human-readable
Markdown file (USER.md) that describes the user. This is richer,
more natural, and editable in any text editor.

Tools:
    read_user_memory    Read the current USER.md
    update_user_memory  Overwrite USER.md with updated content

Philosophy: One Markdown file beats a JSON key-value store.
You can read it, edit it, version-control it.
"""

from bujji.tools.base import register_tool


@register_tool(
    description=(
        "Read the USER.md file — your persistent memory about the user. "
        "Call this at the start of a conversation if you need context about "
        "who the user is, their projects, or their preferences."
    ),
    parameters={"type": "object", "properties": {}},
)
def read_user_memory(_ctx: dict = None) -> str:
    from bujji.identity import read_user_file
    return read_user_file(_ctx["workspace"])


@register_tool(
    description=(
        "Update USER.md — your persistent memory about the user. "
        "Call this whenever the user shares something worth remembering: "
        "their name, preferences, current projects, tech stack, or any context "
        "that will be useful in future sessions. "
        "Pass the COMPLETE new content of USER.md — include existing info plus the new info. "
        "Write it as natural Markdown, not key-value pairs."
    ),
    parameters={
        "type": "object",
        "required": ["content"],
        "properties": {
            "content": {
                "type":        "string",
                "description": (
                    "The full new content for USER.md. "
                    "Include everything — existing facts and new ones. "
                    "Use Markdown headings and bullet points."
                ),
            },
        },
    },
)
def update_user_memory(content: str, _ctx: dict = None) -> str:
    from bujji.identity import update_user_file
    return update_user_file(_ctx["workspace"], content)

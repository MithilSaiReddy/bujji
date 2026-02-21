"""
bujji/tools/utils.py  —  v2
Utility tools: get_time, message (push notification to user).
"""
from __future__ import annotations

import datetime

from bujji.tools.base import ToolContext, register_tool

@register_tool(
    description="Get the current local date, time, and day of the week.",
    parameters={"type": "object", "properties": {}},
)
def get_time(_ctx: ToolContext = None) -> str:
    now = datetime.datetime.now()
    return now.strftime("%A, %Y-%m-%d  %H:%M:%S  (local time)")

@register_tool(
    description=(
        "Send a notification message directly to the user. "
        "Use this in scheduled/heartbeat tasks to proactively inform the user "
        "of results, alerts, or reminders."
    ),
    parameters={
        "type":     "object",
        "required": ["text"],
        "properties": {
            "text": {
                "type":        "string",
                "description": "Message text to send to the user.",
            },
        },
    },
)
def message(text: str, _ctx: ToolContext = None) -> str:
    if _ctx and _ctx.send_message_fn:
        try:
            _ctx.send_message_fn(text)
            return f"Message sent ({len(text)} chars)"
        except Exception as e:
            return f"[MESSAGE ERROR] Failed to send: {e}"
    return f"[MESSAGE] (no channel) {text}"

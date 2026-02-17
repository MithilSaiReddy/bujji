"""
bujji/tools/utils.py
Common utility tools for the agent.
"""
import datetime
from bujji.tools.base import register_tool

@register_tool(
    description="Get the current local date and time.",
    parameters={"type": "object", "properties": {}}
)
def get_time() -> str:
    """Returns the current system time."""
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def message(text: str, _ctx: dict = None) -> str:
    """
    Helper to send a message back to the user via the current channel.
    This is used internally by other tools if they need to push updates.
    """
    if _ctx and _ctx.get("send_message_fn"):
        _ctx["send_message_fn"](text)
    return f"Message sent: {text}"
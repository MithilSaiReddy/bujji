"""
bujji/tools — Tool registry and built-in tools.

Built-in tools (auto-discovered on import):
    web_search    Brave Search API
    read_file     Read a file from disk
    write_file    Write a file to disk
    list_files    List directory contents
    delete_file   Delete a file or directory
    exec          Run a shell command
    get_time      Get the current date/time
    message       Send a message to the user

Adding a new tool
─────────────────
1. Create bujji/tools/mytool.py
2. Decorate your function with @register_tool(description, parameters)
3. Done — ToolRegistry discovers it automatically on next run.
"""

from bujji.tools.base import ToolRegistry, register_tool

# Force import of all built-in tool modules so their @register_tool
# decorators fire even if ToolRegistry hasn't been instantiated yet.
# This also makes them importable directly if needed:
#   from bujji.tools import web_search
from bujji.tools.file_ops import read_file, write_file, list_files, delete_file
from bujji.tools.shell    import exec
from bujji.tools.web      import web_search
from bujji.tools.utils    import get_time, message

__all__ = [
    # Registry
    "ToolRegistry",
    "register_tool",
    # Built-in tools
    "read_file",
    "write_file",
    "list_files",
    "delete_file",
    "exec",
    "web_search",
    "get_time",
    "message",
]
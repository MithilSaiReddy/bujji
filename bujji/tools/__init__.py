"""
bujji/tools — Tool registry and built-in tools.

Built-in tools (auto-discovered via @register_tool):
    exec                Run a shell command
    read_file           Read a file from disk
    write_file          Write (overwrite) a file
    append_file         Append text to a file
    list_files          List directory contents
    delete_file         Delete a file or directory
    web_search          Brave Search API
    get_time            Current date and time
    message             Push a message to the user
    read_user_memory    Read USER.md (persistent memory)
    append_user_memory  Add new facts to USER.md (safe, non-destructive)
    update_user_memory  Replace USER.md entirely

Adding a new tool
─────────────────
1. Create bujji/tools/mytool.py
2. Decorate with @register_tool(description, parameters)
3. That's it — ToolRegistry picks it up automatically (hot-reload included)
"""

from bujji.tools.base     import ToolRegistry, register_tool, ToolContext
from bujji.tools.file_ops import read_file, write_file, append_file, list_files, delete_file
from bujji.tools.shell    import exec
from bujji.tools.web      import web_search
from bujji.tools.utils    import get_time, message
from bujji.tools.memory   import read_user_memory, append_user_memory, update_user_memory

__all__ = [
    "ToolRegistry", "register_tool", "ToolContext",
    "read_file", "write_file", "append_file", "list_files", "delete_file",
    "exec",
    "web_search",
    "get_time", "message",
    "read_user_memory", "append_user_memory", "update_user_memory",
]

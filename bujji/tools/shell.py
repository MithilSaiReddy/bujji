"""
bujji/tools/shell.py
Shell execution tool: exec.
"""

import subprocess

from bujji.tools.base import register_tool


@register_tool(
    description=(
        "Execute a shell command on the local system and return its output. "
        "Use for running scripts, checking system state, installing packages, etc."
    ),
    parameters={
        "type": "object",
        "required": ["command"],
        "properties": {
            "command": {
                "type":        "string",
                "description": "Shell command to run (passed to /bin/sh -c).",
            },
            "timeout": {
                "type":        "integer",
                "description": "Max seconds to wait before killing the process (default 30).",
            },
        },
    },
)
def exec(command: str, timeout: int = 30, _ctx: dict = None) -> str:
    workspace = _ctx["workspace"] if _ctx else None
    restrict  = _ctx["restrict"]  if _ctx else False
    cwd       = str(workspace) if restrict and workspace else None

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=int(timeout),
            cwd=cwd,
        )
        parts = []
        if result.stdout.strip():
            parts.append(result.stdout.strip())
        if result.stderr.strip():
            parts.append(f"[stderr]\n{result.stderr.strip()}")
        if result.returncode != 0:
            parts.append(f"[exit code: {result.returncode}]")
        return "\n".join(parts) or "(no output)"

    except subprocess.TimeoutExpired:
        return f"Command timed out after {timeout}s"
    except Exception as e:
        return f"Exec error: {e}"
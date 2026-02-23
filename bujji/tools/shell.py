"""
bujji/tools/shell.py  —  v2
Shell execution with clean output, proper exit codes, and safe defaults.
"""
from __future__ import annotations

import subprocess

from bujji.tools.base import ToolContext, register_tool

@register_tool(
    description=(
        "Execute a shell command on the local system and return combined stdout + stderr. "
        "Use for system inspection, running scripts, installing packages, file manipulation, "
        "and anything that needs the host OS. "
        "Relative paths run from the workspace directory."
    ),
    parameters={
        "type":     "object",
        "required": ["command"],
        "properties": {
            "command": {
                "type":        "string",
                "description": "Shell command to run (passed to /bin/sh -c).",
            },
            "timeout": {
                "type":        "integer",
                "description": "Max seconds before the process is killed (default: 30, max: 300).",
            },
            "workdir": {
                "type":        "string",
                "description": (
                    "Working directory for the command. "
                    "Default: workspace root. "
                    "Use '.' to keep the workspace root."
                ),
            },
        },
    },
)
def exec(
    command: str,
    timeout: int = 30,
    workdir: str = ".",
    _ctx:    ToolContext = None,
) -> str:
    workspace = _ctx.workspace if _ctx else None
    restrict  = _ctx.restrict  if _ctx else False

    # Determine cwd
    if workspace:
        from pathlib import Path
        cwd_path = (workspace / workdir).resolve()
        if restrict:
            # Refuse paths outside workspace
            try:
                cwd_path.relative_to(workspace.resolve())
            except ValueError:
                return f"[TOOL ERROR] workdir '{workdir}' is outside the workspace."
        cwd = str(cwd_path)
    else:
        cwd = None

    # Cap timeout
    timeout = max(1, min(int(timeout), 300))

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
        )
    except subprocess.TimeoutExpired:
        return f"[TIMEOUT] Command killed after {timeout}s:\n  {command}"
    except Exception as e:
        return f"[ERROR] Could not run command: {e}"

    parts: list[str] = []

    if result.stdout.strip():
        parts.append(result.stdout.strip())
    if result.stderr.strip():
        parts.append(f"[stderr]\n{result.stderr.strip()}")
    if result.returncode != 0:
        parts.append(f"[exit code: {result.returncode}]")

    return "\n".join(parts) if parts else "(no output)"

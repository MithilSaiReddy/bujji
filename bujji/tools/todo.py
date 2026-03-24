"""
bujji/tools/todo.py

Task breakdown and todo list management.
Stores tasks in workspace/todo.md as numbered checklist.

Tools:
    create_todo  - Break a complex task into numbered subtasks
    next_todo    - Get the next pending task (auto-marks complete after execution)
    list_todos   - Show all tasks with their status
    clear_todos  - Remove completed tasks or all tasks
"""
from __future__ import annotations

import datetime
import re
from pathlib import Path

from bujji.tools.base import ToolContext, param, register_tool


TODO_FILE = "todo.md"


def _read_todo(_ctx: ToolContext) -> list[dict]:
    todo_path = _ctx.workspace / TODO_FILE
    if not todo_path.exists():
        return []
    
    content = todo_path.read_text(encoding="utf-8")
    tasks = []
    
    for line in content.split("\n"):
        line = line.strip()
        if not line:
            continue
        match = re.match(r"^(\d+)\.\s*\[([ x])\]\s*(.+)$", line)
        if match:
            num = int(match.group(1))
            done = match.group(2) == "x"
            desc = match.group(3).strip()
            tasks.append({"number": num, "done": done, "description": desc})
    
    return tasks


def _write_todo(_ctx: ToolContext, tasks: list[dict]) -> None:
    todo_path = _ctx.workspace / TODO_FILE
    lines = ["# Todo", ""]
    
    for t in tasks:
        mark = "x" if t["done"] else " "
        lines.append(f"{t['number']}. [{mark}] {t['description']}")
    
    lines.append("")
    lines.append("---")
    lines.append(f"Updated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
    
    todo_path.write_text("\n".join(lines), encoding="utf-8")


def _break_into_tasks(task: str) -> list[str]:
    import requests
    from bujji.config import get_active_provider
    
    from bujji.llm import LLMProvider
    from bujji.config import load_config
    
    cfg = load_config()
    pname, api_key, api_base, model = get_active_provider(cfg)
    if not pname:
        return [task]
    
    llm = LLMProvider(pname, api_key, api_base, model, max_tokens=1024, temperature=0.7)
    
    prompt = f"""Break this task into 3-8 numbered subtasks. Each subtask should be:
- Specific and actionable
- Can be completed in one step
- Clear enough to execute directly

Task: {task}

Respond ONLY with a numbered list, one subtask per line, no other text. Example:
1. First step description
2. Second step description
3. Third step description"""

    try:
        resp = llm.chat([{"role": "user", "content": prompt}], stream=False)
        content = resp["choices"][0]["message"]["content"]
        
        tasks = []
        for line in content.split("\n"):
            line = line.strip()
            match = re.match(r"^\d+[\.\)]\s*(.+)$", line)
            if match:
                tasks.append(match.group(1).strip())
        
        return tasks if tasks else [task]
    except Exception:
        return [task]


@register_tool(
    description=(
        "Break a complex task into smaller numbered subtasks and save to todo.md. "
        "Use this when a user request has multiple steps that would benefit from being tracked."
    ),
    params=[
        param("task", "The complex task to break down into subtasks"),
    ]
)
def create_todo(task: str, _ctx: ToolContext = None) -> str:
    if not task:
        return "[TOOL ERROR] Task description is required."
    
    subtasks = _break_into_tasks(task)
    
    tasks = []
    for i, desc in enumerate(subtasks, 1):
        tasks.append({"number": i, "done": False, "description": desc})
    
    _write_todo(_ctx, tasks)
    
    preview = "\n".join([f"{t['number']}. [ ] {t['description'][:60]}" + ("..." if len(t['description']) > 60 else "") for t in tasks[:5]])
    if len(tasks) > 5:
        preview += f"\n... and {len(tasks) - 5} more"
    
    return f"Created {len(tasks)} tasks in {TODO_FILE}:\n\n{preview}\n\nUse next_todo() to start working on them."


@register_tool(
    description=(
        "Get the next pending task from todo.md and optionally mark the previous task as complete. "
        "Call this after successfully completing a task to automatically get the next one. "
        "This enables automatic continuation through all pending tasks."
    ),
    params=[
        param("complete_previous", "Mark the previous task as complete before getting next", type="boolean", default=True),
    ]
)
def next_todo(complete_previous: bool = True, _ctx: ToolContext = None) -> str:
    tasks = _read_todo(_ctx)
    
    if not tasks:
        return f"No tasks in {TODO_FILE}. Use create_todo() to create one."
    
    pending = [t for t in tasks if not t["done"]]
    
    if complete_previous:
        for t in tasks:
            if not t["done"]:
                t["done"] = True
                _write_todo(_ctx, tasks)
                break
    
    tasks = _read_todo(_ctx)
    pending = [t for t in tasks if not t["done"]]
    
    if not pending:
        return f"[DONE] All {len(tasks)} tasks completed! ✓"
    
    next_task = pending[0]
    remaining = len(pending)
    
    return f"[TASK {next_task['number']}/{len(tasks)}] {next_task['description']}\n\n({remaining} task{'s' if remaining > 1 else ''} remaining)"


@register_tool(
    description="List all tasks from todo.md with their completion status.",
)
def list_todos(_ctx: ToolContext = None) -> str:
    tasks = _read_todo(_ctx)
    
    if not tasks:
        return f"No tasks in {TODO_FILE}. Use create_todo() to create one."
    
    done = sum(1 for t in tasks if t["done"])
    pending = len(tasks) - done
    
    lines = [f"# Todo ({done}/{len(tasks)} completed)", ""]
    
    for t in tasks:
        mark = "✓" if t["done"] else " "
        lines.append(f"{mark} {t['number']}. {t['description']}")
    
    lines.append("")
    lines.append(f"Pending: {pending} | Completed: {done}")
    
    return "\n".join(lines)


@register_tool(
    description="Clear completed tasks or all tasks from todo.md.",
    params=[
        param("mode", "What to clear", enum=["completed", "all"], default="completed"),
    ]
)
def clear_todos(mode: str = "completed", _ctx: ToolContext = None) -> str:
    if mode == "all":
        todo_path = _ctx.workspace / TODO_FILE
        if todo_path.exists():
            todo_path.unlink()
        return "All tasks cleared."
    
    tasks = _read_todo(_ctx)
    remaining = [t for t in tasks if not t["done"]]
    
    if not remaining:
        return "No completed tasks to clear."
    
    _write_todo(_ctx, remaining)
    cleared = len(tasks) - len(remaining)
    return f"Cleared {cleared} completed task{'s' if cleared > 1 else ''}."

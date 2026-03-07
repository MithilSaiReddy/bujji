# bujji/tools/subagents.py
#
# Drop this file into bujji/tools/ — it's hot-reloaded automatically.
# No changes needed anywhere else in the codebase.
#
# Gives the main agent two new tools:
#   spawn_subagent  — run a one-shot task with a specialist agent
#   agent_pipeline  — run a chain of specialist agents, each feeding the next

from __future__ import annotations

import threading
from typing import Optional

from bujji.tools.base import ToolContext, register_tool

# ─────────────────────────────────────────────
# Internal helper
# ─────────────────────────────────────────────

def _run_subagent(
    role: str,
    task: str,
    ctx: ToolContext,
    extra_tools: list[str] | None = None,
    max_iterations: int = 10,
) -> str:
    """
    Spins up a fresh AgentLoop with a custom system prompt derived from `role`,
    runs `task` through it once, and returns the final text response.

    Imported lazily so the tool file stays loadable even before bujji.agent
    is fully initialised (e.g. during mtime hot-reload scan).
    """
    # Lazy import — keeps circular-import risk zero
    from bujji.agent import AgentLoop
    from bujji.identity import IdentityManager

    cfg = ctx.cfg

    # ── Build a minimal identity for the sub-agent ──────────────────────────
    # We give it the same SOUL/USER context as the parent so it shares values
    # and memory, but override the IDENTITY with the requested role.
    identity = IdentityManager(cfg)

    soul      = identity.load("SOUL")       # shared ethics / values
    user_mem  = identity.load("USER")       # shared memory about the user
    agent_md  = identity.load("AGENT")      # shared tool descriptions

    system_prompt = f"""You are a specialised sub-agent with the following role:

{role}

─── Shared context ───────────────────────────────────────────────
{soul}

─── Memory about the user ────────────────────────────────────────
{user_mem}

─── Available tools ──────────────────────────────────────────────
{agent_md}
──────────────────────────────────────────────────────────────────

Important rules:
- Focus ONLY on the task given to you.
- Be concise. Return a clear, structured result the parent agent can use.
- Do NOT ask clarifying questions — make your best attempt and explain
  any assumptions at the end.
"""

    # ── Spin up the child AgentLoop ─────────────────────────────────────────
    child = AgentLoop(
        cfg=cfg,
        system_prompt_override=system_prompt,
        max_tool_iterations=max_iterations,
    )

    # Collect streamed tokens into a string (no live streaming for sub-agents)
    tokens: list[str] = []

    result = child.run(
        message=task,
        history=[],
        on_token=lambda t: tokens.append(t),
    )

    # AgentLoop.run() returns the final text; fall back to joined tokens
    return result if result else "".join(tokens)


# ─────────────────────────────────────────────
# Tool 1 — spawn_subagent
# ─────────────────────────────────────────────

@register_tool(
    description=(
        "Spawn a specialist sub-agent to handle a specific task. "
        "The sub-agent runs independently, has access to all the same tools, "
        "and returns a structured result. "
        "Use this to delegate focused work — research, coding, summarisation, "
        "planning, data analysis — while you orchestrate the bigger picture.\n\n"
        "Built-in role shortcuts (use exactly as shown, or write your own):\n"
        "  'researcher'  — web search, summarise, cite sources\n"
        "  'coder'       — write, review, or debug code\n"
        "  'planner'     — break a goal into ordered subtasks\n"
        "  'writer'      — draft documents, emails, or reports\n"
        "  'analyst'     — read files/data and extract insights\n"
        "  'memory'      — read and update USER.md with new facts\n"
        "Or pass any free-form role description."
    ),
    parameters={
        "type": "object",
        "required": ["role", "task"],
        "properties": {
            "role": {
                "type": "string",
                "description": (
                    "Role or persona for the sub-agent. "
                    "Use a shortcut ('researcher', 'coder', 'planner', "
                    "'writer', 'analyst', 'memory') or write a custom description."
                ),
            },
            "task": {
                "type": "string",
                "description": (
                    "The complete, self-contained task for the sub-agent. "
                    "Include all context it needs — it has no memory of the "
                    "current conversation."
                ),
            },
            "max_iterations": {
                "type": "integer",
                "description": "Max tool-use iterations for the sub-agent (default: 10).",
                "default": 10,
            },
        },
    },
)
def spawn_subagent(
    role: str,
    task: str,
    max_iterations: int = 10,
    _ctx: ToolContext = None,
) -> str:
    # ── Expand role shortcuts into full personas ─────────────────────────────
    ROLE_PRESETS = {
        "researcher": (
            "You are an expert researcher. Your job is to search the web, "
            "gather accurate information, and return a well-structured summary "
            "with key facts clearly separated. Always cite your sources."
        ),
        "coder": (
            "You are an expert software engineer. Write clean, well-commented "
            "code. If reviewing, identify bugs and suggest fixes with explanations. "
            "Always specify the language and any dependencies."
        ),
        "planner": (
            "You are a strategic planner. Break the given goal into a clear, "
            "numbered list of actionable subtasks in logical order. "
            "For each step note what tool or resource is needed."
        ),
        "writer": (
            "You are a professional writer and editor. Produce polished, "
            "well-structured documents. Match the requested tone and format. "
            "Proofread your output before returning it."
        ),
        "analyst": (
            "You are a data and document analyst. Read the provided files or data, "
            "extract key insights, identify patterns, and present findings clearly "
            "with supporting evidence."
        ),
        "memory": (
            "You are a memory manager. Your only job is to read the current USER.md, "
            "identify new facts provided in the task, and append them cleanly "
            "without duplicating existing entries."
        ),
    }

    resolved_role = ROLE_PRESETS.get(role.lower().strip(), role)

    try:
        result = _run_subagent(
            role=resolved_role,
            task=task,
            ctx=_ctx,
            max_iterations=max_iterations,
        )
        return f"[Sub-agent: {role}]\n\n{result}"
    except Exception as e:
        return f"[TOOL ERROR] spawn_subagent failed: {e}"


# ─────────────────────────────────────────────
# Tool 2 — agent_pipeline
# ─────────────────────────────────────────────

@register_tool(
    description=(
        "Run a chain of sub-agents in sequence. "
        "Each agent's output is automatically passed as input to the next. "
        "Perfect for multi-step workflows: e.g. research → analyse → write report.\n\n"
        "Example stages:\n"
        '  [{"role": "researcher", "task": "Find recent AI news"},\n'
        '   {"role": "analyst",    "task": "Identify the 3 biggest trends from: {previous}"},\n'
        '   {"role": "writer",     "task": "Write a 200-word briefing from: {previous}"}]\n\n'
        "Use {previous} in a task string to insert the previous agent's output."
    ),
    parameters={
        "type": "object",
        "required": ["stages"],
        "properties": {
            "stages": {
                "type": "array",
                "description": "Ordered list of {role, task} objects. Use {previous} to pass prior output.",
                "items": {
                    "type": "object",
                    "required": ["role", "task"],
                    "properties": {
                        "role": {"type": "string"},
                        "task": {"type": "string"},
                        "max_iterations": {"type": "integer", "default": 10},
                    },
                },
            }
        },
    },
)
def agent_pipeline(
    stages: list[dict],
    _ctx: ToolContext = None,
) -> str:
    if not stages:
        return "[TOOL ERROR] agent_pipeline: stages list is empty."

    previous_output = ""
    log: list[str] = []

    for i, stage in enumerate(stages):
        role = stage.get("role", "assistant")
        task = stage.get("task", "")
        max_iter = stage.get("max_iterations", 10)

        # Inject previous output if the task references it
        if "{previous}" in task:
            task = task.replace("{previous}", previous_output)

        try:
            result = spawn_subagent(
                role=role,
                task=task,
                max_iterations=max_iter,
                _ctx=_ctx,
            )
            previous_output = result
            log.append(f"── Stage {i+1} [{role}] ──\n{result}")
        except Exception as e:
            error_msg = f"[TOOL ERROR] agent_pipeline stage {i+1} ({role}) failed: {e}"
            log.append(error_msg)
            break  # Stop pipeline on failure

    return "\n\n".join(log)
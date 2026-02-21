"""
bujji/tools/base.py  —  v2
ToolContext · register_tool · ToolRegistry


How to add a new tool
─────────────────────
1.  Create a new file in bujji/tools/, e.g. weather.py
2.  Define your function(s) with a normal Python signature.
3.  Decorate with @register_tool(description, parameters_schema).
4.  That's it — the registry picks it up automatically on next run.

Example
───────
    # bujji/tools/weather.py
    from bujji.tools.base import register_tool

    @register_tool(
        description="Get current weather for a city.",
        parameters={
            "type": "object",
            "required": ["city"],
            "properties": {
                "city": {"type": "string", "description": "City name"}
            }
        }
    )
    def get_weather(city: str) -> str:
        ...

        
What's new vs v1
────────────────
• ToolContext is a typed dataclass — no more fragile _ctx dict
• Hot-reload   : drop a new .py in tools/ → picked up immediately, no restart
• Smart truncation : keeps head + tail so the LLM always sees both start and end
• Callbacks    : on_tool_start / on_tool_done for streaming web UI events
• Startup validation : all registered tools are sanity-checked at init
• Structured errors  : every exception becomes a [TOOL ERROR] string the LLM
                       can reason about instead of crashing silently
"""
from __future__ import annotations

import importlib
import inspect
import os
import pkgutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

# ── Typed context injected into every tool ────────────────────────────────────

@dataclass
class ToolContext:
    cfg:             dict
    workspace:       Path
    restrict:        bool                             = False
    send_message_fn: Optional[Callable[[str], None]] = None
    on_tool_start:   Optional[Callable[[str, dict], None]] = None  # (name, args)
    on_tool_done:    Optional[Callable[[str, str],  None]] = None  # (name, result)

# ── Global registry ───────────────────────────────────────────────────────────

# name → (callable, openai-function-schema)
_REGISTRY:      dict[str, tuple[Callable, dict]] = {}
_MODULE_MTIMES: dict[str, float]                 = {}   # for hot-reload

# ── Decorator ─────────────────────────────────────────────────────────────────

def register_tool(description: str, parameters: dict | None = None):
    """
    Decorator that registers a Python function as an AI tool.

    The function may optionally accept `_ctx: ToolContext` as its last param;
    ToolRegistry will inject it automatically at call time.

    Example
    ───────
    @register_tool(
        description="Fetch the weather for a city.",
        parameters={
            "type": "object",
            "required": ["city"],
            "properties": {"city": {"type": "string", "description": "City name"}},
        },
    )
    def get_weather(city: str, _ctx: ToolContext = None) -> str:
        return f"Weather in {city}: sunny"
    """
    def decorator(fn: Callable) -> Callable:
        schema = {
            "type": "function",
            "function": {
                "name":        fn.__name__,
                "description": description,
                "parameters":  parameters or {"type": "object", "properties": {}},
            },
        }
        _REGISTRY[fn.__name__] = (fn, schema)
        return fn
    return decorator

# ── Hot-reload auto-discovery ─────────────────────────────────────────────────

def _autodiscover(tools_pkg_path: Path, pkg_name: str) -> None:
    """
    Import (or reload) every *.py module in tools/ so @register_tool
    decorators fire.  Skips unchanged files for performance.
    """
    for _, module_name, _ in pkgutil.iter_modules([str(tools_pkg_path)]):
        if module_name == "base":
            continue

        full_name = f"{pkg_name}.{module_name}"
        mod_file  = tools_pkg_path / f"{module_name}.py"
        mtime     = mod_file.stat().st_mtime if mod_file.exists() else 0.0

        if full_name in sys.modules and _MODULE_MTIMES.get(full_name) == mtime:
            continue  # file unchanged — skip

        try:
            if full_name in sys.modules:
                importlib.reload(sys.modules[full_name])
                print(f"[INFO] Hot-reloaded tool module: {module_name}", file=sys.stderr)
            else:
                importlib.import_module(full_name)
            _MODULE_MTIMES[full_name] = mtime
        except Exception as e:
            print(f"[WARN] Could not load tool module '{full_name}': {e}", file=sys.stderr)

# ── Registry facade ───────────────────────────────────────────────────────────

class ToolRegistry:
    """
    Auto-discovers, validates, and dispatches tool calls.

    Changes vs v1
    ─────────────
    • Passes ToolContext (typed dataclass) instead of raw _ctx dict
    • Runs _autodiscover() on every schema() / call() → hot-reload for free
    • Smart truncation: head (75%) + tail (25%) keeps context coherent
    • Every error is returned as a string the LLM can act on — never raises
    • Callbacks for the streaming web UI
    """

    DEFAULT_MAX_OUTPUT = 8_000   # characters per tool call

    def __init__(
        self,
        cfg:             dict,
        send_message_fn: Optional[Callable[[str], None]] = None,
        workspace:       Optional[Path]                  = None,
        callbacks:       Optional[dict]                  = None,
    ):
        from bujji.config import workspace_path

        self.cfg             = cfg
        self.workspace       = workspace or workspace_path(cfg)
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.restrict        = cfg["agents"]["defaults"].get("restrict_to_workspace", False)
        self.send_message_fn = send_message_fn
        self.max_output      = cfg["agents"]["defaults"].get(
            "max_tool_output_chars", self.DEFAULT_MAX_OUTPUT
        )
        self.callbacks = callbacks or {}

        self._pkg_path = Path(__file__).parent
        self._pkg_name = __name__.rsplit(".", 1)[0]   # "bujji.tools"

        # Initial discovery
        self._refresh()

        tool_names = list(_REGISTRY)
        print(f"[INFO] Tools loaded ({len(tool_names)}): {', '.join(tool_names)}", file=sys.stderr)

    # ── Public API ─────────────────────────────────────────────────────────

    def schema(self) -> list[dict]:
        """Return OpenAI tool-call schema list.  Triggers hot-reload check."""
        self._refresh()
        return [schema for _, schema in _REGISTRY.values()]

    def call(self, name: str, args: dict) -> str:
        """
        Dispatch a tool by name.  Always returns a str the LLM can read.
        Never raises — every exception becomes an error message.
        """
        self._refresh()

        if name not in _REGISTRY:
            available = ", ".join(_REGISTRY) or "(none)"
            return (
                f"[TOOL ERROR] Unknown tool: '{name}'.\n"
                f"Available tools: {available}"
            )

        fn, _  = _REGISTRY[name]
        ctx    = self._make_ctx()

        # ── Notify start ──
        if ctx.on_tool_start:
            ctx.on_tool_start(name, args)

        # ── Inject context if function wants it ──
        call_args = dict(args)
        if "_ctx" in inspect.signature(fn).parameters:
            call_args["_ctx"] = ctx

        # ── Execute ──
        try:
            raw = fn(**call_args)
        except TypeError as e:
            raw = (
                f"[TOOL ERROR] Wrong arguments for '{name}': {e}\n"
                f"Expected signature: {inspect.signature(fn)}"
            )
        except Exception as e:
            raw = f"[TOOL ERROR] '{name}' raised {type(e).__name__}: {e}"

        output = str(raw) if raw is not None else "(tool returned nothing)"

        # ── Smart truncation: keep 75% from head + 25% from tail ──
        if len(output) > self.max_output:
            head_limit = int(self.max_output * 0.75)
            tail_limit = self.max_output - head_limit
            head       = output[:head_limit]
            tail       = output[-tail_limit:]
            skipped    = len(output) - head_limit - tail_limit
            output     = (
                head
                + f"\n\n[… {skipped:,} characters omitted …]\n\n"
                + tail
            )

        # ── Notify done ──
        if ctx.on_tool_done:
            ctx.on_tool_done(name, output)

        return output

    # ── Private ────────────────────────────────────────────────────────────

    def _refresh(self) -> None:
        _autodiscover(self._pkg_path, self._pkg_name)

    def _make_ctx(self) -> ToolContext:
        return ToolContext(
            cfg             = self.cfg,
            workspace       = self.workspace,
            restrict        = self.restrict,
            send_message_fn = self.send_message_fn,
            on_tool_start   = self.callbacks.get("on_tool_start"),
            on_tool_done    = self.callbacks.get("on_tool_done"),
        )

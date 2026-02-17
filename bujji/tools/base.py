"""
bujji/tools/base.py
ToolRegistry — auto-discovers and registers tools from sibling modules.

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
"""

import importlib
import inspect
import pkgutil
import sys
from pathlib import Path
from typing import Callable

# ── Global function registry ──────────────────────────────────────────────────
# Maps tool_name -> (callable, openai_function_schema)
_REGISTRY: dict[str, tuple[Callable, dict]] = {}


def register_tool(description: str, parameters: dict | None = None):
    """
    Decorator that registers a plain Python function as an AI tool.

    @register_tool(
        description="Search the web.",
        parameters={"type": "object", "required": ["query"],
                    "properties": {"query": {"type": "string"}}}
    )
    def web_search(query: str) -> str:
        ...
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


def _autodiscover():
    """
    Import every module inside bujji/tools/ so their @register_tool
    decorators fire and populate _REGISTRY.
    """
    tools_pkg_path = Path(__file__).parent
    pkg_name       = __name__.rsplit(".", 1)[0]   # "bujji.tools"

    for finder, module_name, _ in pkgutil.iter_modules([str(tools_pkg_path)]):
        if module_name == "base":
            continue
        full_name = f"{pkg_name}.{module_name}"
        if full_name not in sys.modules:
            try:
                importlib.import_module(full_name)
            except Exception as e:
                print(f"[WARN] Could not load tool module {full_name}: {e}",
                      file=sys.stderr)


class ToolRegistry:
    """
    Facade that auto-discovers all tools from bujji/tools/*.py,
    injects runtime context (config, workspace, send_message_fn),
    and provides the call() / schema() interface for the agent loop.
    """

    def __init__(self, cfg: dict, send_message_fn=None, workspace=None):
        from bujji.config import workspace_path

        self.cfg              = cfg
        self.workspace        = workspace or workspace_path(cfg)
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.restrict         = cfg["agents"]["defaults"].get("restrict_to_workspace", False)
        self.send_message_fn  = send_message_fn

        # Build a context dict passed into every tool that needs it
        self._ctx = {
            "cfg":             cfg,
            "workspace":       self.workspace,
            "restrict":        self.restrict,
            "send_message_fn": send_message_fn,
        }

        _autodiscover()

    # ── Public interface ──────────────────────────────────────────────────

    def schema(self) -> list[dict]:
        """Return the OpenAI tool schema list for all registered tools."""
        return [schema for _, schema in _REGISTRY.values()]

    def call(self, name: str, args: dict) -> str:
        """Dispatch a tool call by name with the given arguments."""
        if name not in _REGISTRY:
            return f"Unknown tool: {name}"

        fn, _ = _REGISTRY[name]

        # Inject _ctx if the function accepts it
        sig    = inspect.signature(fn)
        params = sig.parameters
        if "_ctx" in params:
            args = {**args, "_ctx": self._ctx}

        try:
            return fn(**args)
        except TypeError as e:
            return f"Tool argument error ({name}): {e}"
        except Exception as e:
            return f"Tool error ({name}): {e}"
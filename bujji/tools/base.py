"""
bujji/tools/base.py  —  v3.1

ToolContext · register_tool · ToolRegistry
+ param()             — one-liner parameter declaration (kills JSON schema boilerplate)
+ ToolContext.cred()  — clean credential access with friendly missing-key error
+ HttpClient          — zero-boilerplate HTTP for any REST API

Fix in v3.1: HttpClient._url() no longer strips leading slash from path,
             preventing base_url + path merging into e.g. "/v1search" instead of "/v1/search"
"""
from __future__ import annotations

import importlib
import inspect
import pkgutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

_MISSING = object()  # sentinel for param() default detection


# ─────────────────────────────────────────────────────────────────────────────
#  param() — one-liner parameter declaration
# ─────────────────────────────────────────────────────────────────────────────

def param(
    name:        str,
    description: str,
    type:        str  = "string",
    required:    bool = True,
    default:     Any  = _MISSING,
    enum:        list | None = None,
    items:       dict | None = None,
) -> dict:
    """
    Declare a single tool parameter — replaces the verbose JSON schema dict.

    Examples
    ────────
    param("query",   "Search query")                               # required string
    param("limit",   "Max results",  type="integer", default=10)   # optional int
    param("status",  "Task status",  enum=["open", "closed"])      # enum string
    param("tags",    "Tag list",     type="array",   default=[])   # optional array
    param("verbose", "Debug output", type="boolean", default=False)
    """
    if default is not _MISSING:
        required = False

    schema: dict = {"type": type, "description": description}
    if enum:
        schema["enum"] = enum
    if type == "array" and items:
        schema["items"] = items
    elif type == "array" and not items:
        schema["items"] = {"type": "string"}  # sensible default

    return {"_name": name, "_required": required, "_schema": schema}


def _params_to_schema(params: list[dict]) -> dict:
    """Convert a list of param() results into an OpenAI-style JSON schema."""
    properties = {}
    required   = []
    for p in params:
        name = p["_name"]
        properties[name] = p["_schema"]
        if p["_required"]:
            required.append(name)
    out: dict = {"type": "object", "properties": properties}
    if required:
        out["required"] = required
    return out


# ─────────────────────────────────────────────────────────────────────────────
#  ToolContext — injected into every tool call
# ─────────────────────────────────────────────────────────────────────────────

class ToolCredentialError(RuntimeError):
    """Raised when a required credential is missing. Turned into a helpful string."""
    pass


@dataclass
class ToolContext:
    cfg:             dict
    workspace:       Path
    restrict:        bool                                   = False
    send_message_fn: Optional[Callable[[str], None]]       = None
    on_tool_start:   Optional[Callable[[str, dict], None]] = None
    on_tool_done:    Optional[Callable[[str, str],  None]] = None

    # ── credential helper ─────────────────────────────────────────────────

    def cred(self, dotpath: str, *, required: bool = True) -> str:
        """
        Get a credential from config using dot-notation.

        Credentials live under cfg["tools"][<service>][<key>].

        Examples
        ────────
        _ctx.cred("notion.api_key")       → cfg["tools"]["notion"]["api_key"]
        _ctx.cred("gmail.access_token")   → cfg["tools"]["gmail"]["access_token"]
        _ctx.cred("openweather.api_key")  → cfg["tools"]["openweather"]["api_key"]

        If the value is missing and required=True (default) a ToolCredentialError
        is raised — which becomes a clean "not configured" message the LLM sees.
        """
        parts = dotpath.split(".")
        if len(parts) != 2:
            raise ValueError(f"cred() path must be 'service.key', got: '{dotpath}'")
        service, key = parts
        value = (
            self.cfg
                .get("tools", {})
                .get(service, {})
                .get(key, "")
        )
        if not value and required:
            raise ToolCredentialError(
                f"[{service}] '{key}' not configured.\n"
                f"  → Add it in the web UI:  Settings → Tools → {service.title()}\n"
                f"  → Or in config.json:     tools.{service}.{key}"
            )
        return value

    def creds(self, service: str) -> dict:
        """
        Return all stored credentials for a service as a dict.

        Example
        ───────
        keys = _ctx.creds("gmail")
        # → {"access_token": "...", "refresh_token": "...", ...}
        """
        return dict(self.cfg.get("tools", {}).get(service, {}))


# ─────────────────────────────────────────────────────────────────────────────
#  HttpClient — zero-boilerplate REST calls
# ─────────────────────────────────────────────────────────────────────────────

class HttpClient:
    """
    Thin, synchronous HTTP client for REST APIs.

    • Auto-parses JSON responses
    • Clean error messages (includes status code + body snippet)
    • base_url so you only write paths in each call
    • All methods accept arbitrary **kwargs forwarded to requests

    Usage
    ─────
    client = HttpClient(
        base_url = "https://api.notion.com/v1",
        headers  = {
            "Authorization":  "Bearer " + _ctx.cred("notion.api_key"),
            "Notion-Version": "2022-06-28",
        },
    )
    pages  = client.get("/search", json={"query": "meeting notes"})
    result = client.post("/pages", json={...})
    client.patch(f"/pages/{page_id}", json={"archived": True})
    """

    def __init__(
        self,
        base_url: str = "",
        headers:  dict | None = None,
        timeout:  int = 15,
    ):
        self.base_url = base_url.rstrip("/")   # strip trailing slash once
        self.headers  = headers or {}
        self.timeout  = timeout
        self._session = None                   # lazy-init

    def _sess(self):
        if self._session is None:
            try:
                import requests
                self._session = requests.Session()
                self._session.headers.update(self.headers)
            except ImportError:
                raise RuntimeError("requests not installed.\nRun: pip install requests")
        return self._session

    def _url(self, path: str) -> str:
        """
        Merge base_url + path correctly.

        ✓  base="https://api.notion.com/v1"  path="/search"
           → "https://api.notion.com/v1/search"

        ✓  base="https://api.example.com"    path="users/me"
           → "https://api.example.com/users/me"

        ✓  absolute path passed directly
           → returned as-is
        """
        if path.startswith("http"):
            return path                        # absolute URL — use as-is

        # Ensure exactly one slash between base and path
        # base already has no trailing slash (stripped in __init__)
        # path may or may not have a leading slash — normalise to always have one
        if not path.startswith("/"):
            path = "/" + path

        return self.base_url + path            # "base" + "/path"  ✓

    def _call(self, method: str, path: str, **kwargs) -> Any:
        import requests as _req
        url = self._url(path)
        try:
            r = self._sess().request(method, url, timeout=self.timeout, **kwargs)
        except _req.exceptions.ConnectionError:
            raise RuntimeError(
                f"Cannot connect to {url}.\n"
                "Check your network connection and the API base URL."
            )
        except _req.exceptions.Timeout:
            raise RuntimeError(f"Request to {url} timed out after {self.timeout}s.")

        if not r.ok:
            try:
                body = r.json()
                msg  = (
                    body.get("message")
                    or (body.get("error", {}).get("message") if isinstance(body.get("error"), dict) else None)
                    or body.get("error")
                    or body.get("detail")
                    or r.text[:300]
                )
            except Exception:
                msg = r.text[:300]
            raise RuntimeError(f"HTTP {r.status_code} from {url}: {msg}")

        ct = r.headers.get("Content-Type", "")
        if "json" in ct:
            return r.json()
        if r.content:
            return r.text
        return {}

    # ── Convenience methods ───────────────────────────────────────────────

    def get(self, path: str, params: dict | None = None, **kwargs) -> Any:
        return self._call("GET", path, params=params, **kwargs)

    def post(self, path: str, json: Any = None, data: Any = None, **kwargs) -> Any:
        return self._call("POST", path, json=json, data=data, **kwargs)

    def patch(self, path: str, json: Any = None, **kwargs) -> Any:
        return self._call("PATCH", path, json=json, **kwargs)

    def put(self, path: str, json: Any = None, **kwargs) -> Any:
        return self._call("PUT", path, json=json, **kwargs)

    def delete(self, path: str, **kwargs) -> Any:
        return self._call("DELETE", path, **kwargs)


# ─────────────────────────────────────────────────────────────────────────────
#  register_tool — accepts both params= shorthand and raw parameters=
# ─────────────────────────────────────────────────────────────────────────────

def register_tool(
    description: str,
    parameters:  dict | None       = None,
    params:      list[dict] | None = None,
):
    """
    Decorator that registers a Python function as an AI tool.

    Two ways to declare parameters:

    ── New way (recommended) ────────────────────────────────────────────────
    @register_tool(
        description="Get weather for a city.",
        params=[
            param("city",  "City name"),
            param("units", "celsius or fahrenheit",
                  enum=["celsius", "fahrenheit"], default="celsius"),
        ]
    )

    ── Old way (still works — backwards compatible) ─────────────────────────
    @register_tool(
        description="Get weather for a city.",
        parameters={
            "type": "object",
            "required": ["city"],
            "properties": {"city": {"type": "string", "description": "City name"}},
        }
    )
    """
    if params is not None:
        schema_dict = _params_to_schema(params)
    elif parameters is not None:
        schema_dict = parameters
    else:
        schema_dict = {"type": "object", "properties": {}}

    def decorator(fn: Callable) -> Callable:
        schema = {
            "type": "function",
            "function": {
                "name":        fn.__name__,
                "description": description,
                "parameters":  schema_dict,
            },
        }
        _REGISTRY[fn.__name__] = (fn, schema)
        return fn
    return decorator


# ─────────────────────────────────────────────────────────────────────────────
#  Global registry
# ─────────────────────────────────────────────────────────────────────────────

_REGISTRY:      dict[str, tuple[Callable, dict]] = {}
_MODULE_MTIMES: dict[str, float]                 = {}


def _autodiscover(tools_pkg_path: Path, pkg_name: str) -> None:
    """
    Import (or reload) every *.py module in tools/ so @register_tool
    decorators fire.  Skips unchanged files via mtime for performance.
    """
    for _, module_name, _ in pkgutil.iter_modules([str(tools_pkg_path)]):
        if module_name in ("base", "TEMPLATE"):
            continue

        full_name = f"{pkg_name}.{module_name}"
        mod_file  = tools_pkg_path / f"{module_name}.py"
        mtime     = mod_file.stat().st_mtime if mod_file.exists() else 0.0

        if full_name in sys.modules and _MODULE_MTIMES.get(full_name) == mtime:
            continue  # unchanged — skip

        try:
            if full_name in sys.modules:
                importlib.reload(sys.modules[full_name])
                print(f"[INFO] Hot-reloaded tool module: {module_name}", file=sys.stderr)
            else:
                importlib.import_module(full_name)
            _MODULE_MTIMES[full_name] = mtime
        except Exception as e:
            print(f"[WARN] Could not load tool module '{full_name}': {e}", file=sys.stderr)


# ─────────────────────────────────────────────────────────────────────────────
#  ToolRegistry — auto-discovers and dispatches tools
# ─────────────────────────────────────────────────────────────────────────────

class ToolRegistry:
    DEFAULT_MAX_OUTPUT = 8_000

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

        self._refresh()
        tool_names = list(_REGISTRY)
        print(f"[INFO] Tools loaded ({len(tool_names)}): {', '.join(tool_names)}", file=sys.stderr)

    def schema(self) -> list[dict]:
        """Return OpenAI tool-call schema list. Triggers hot-reload check."""
        self._refresh()
        return [schema for _, schema in _REGISTRY.values()]

    def call(self, name: str, args: dict) -> str:
        """
        Dispatch a tool by name. Always returns str — never raises.
        ToolCredentialError gets a clean "not configured" message.
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

        if ctx.on_tool_start:
            ctx.on_tool_start(name, args)

        call_args = dict(args)
        if "_ctx" in inspect.signature(fn).parameters:
            call_args["_ctx"] = ctx

        try:
            raw = fn(**call_args)
        except ToolCredentialError as e:
            raw = str(e)
        except TypeError as e:
            raw = (
                f"[TOOL ERROR] Wrong arguments for '{name}': {e}\n"
                f"Expected signature: {inspect.signature(fn)}"
            )
        except Exception as e:
            raw = f"[TOOL ERROR] '{name}' raised {type(e).__name__}: {e}"

        output = str(raw) if raw is not None else "(tool returned nothing)"

        # Smart truncation: keep 75% head + 25% tail
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

        if ctx.on_tool_done:
            ctx.on_tool_done(name, output)

        return output

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
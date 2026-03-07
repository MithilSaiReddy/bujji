"""
bujji/tools/TEMPLATE.py

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  BUJJI TOOL TEMPLATE  —  copy this file to make a new tool
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

STEPS
─────
1. cp bujji/tools/TEMPLATE.py  bujji/tools/mytool.py
2. Replace MYSERVICE with your service name (e.g. github, weather, gmail)
3. Fill in the HttpClient base_url + auth headers
4. Add your credential key(s) to ~/.bujji/config.json  (see CONFIG section)
5. Write your tool functions — save the file, it's live instantly. No restart.

CONFIG  (~/.bujji/config.json)
──────────────────────────────
{
  "tools": {
    "MYSERVICE": {
      "api_key": "your-key-here"
    }
  }
}

That's all the setup needed.
"""
from __future__ import annotations

# ── Always import these three ──────────────────────────────────────────────
from bujji.tools.base import HttpClient, ToolContext, param, register_tool


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  STEP 1 — Shared client factory
#  One function that returns a configured HttpClient.
#  All your tools call this instead of repeating auth/headers.
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _client(_ctx: ToolContext) -> HttpClient:
    return HttpClient(
        base_url = "https://api.MYSERVICE.com/v1",   # ← change this
        headers  = {
            # Most APIs use one of these auth patterns — pick yours:
            "Authorization": "Bearer " + _ctx.cred("MYSERVICE.api_key"),
            # "Authorization": "token " + _ctx.cred("MYSERVICE.api_key"),
            # "X-API-Key":     _ctx.cred("MYSERVICE.api_key"),
            "Content-Type":  "application/json",
        },
    )

# ── cred() path format:  "service_name.key_name"
#    Maps to:  config.json → tools → service_name → key_name
#
#  Multiple credentials?  No problem:
#    _ctx.cred("gmail.client_id")
#    _ctx.cred("gmail.client_secret")
#    _ctx.cred("gmail.refresh_token")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  STEP 2 — Write your tools
#
#  Rules:
#  • Always return a str  (the agent reads it as text)
#  • Accept _ctx: ToolContext = None  as the last parameter
#  • Use param() to declare parameters — no JSON schema needed
#  • Use _client(_ctx) to make HTTP calls
#  • Errors from HttpClient are caught by ToolRegistry automatically
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


# ── Example: Simple GET tool ───────────────────────────────────────────────

@register_tool(
    description="One sentence: what does this tool do and when should the agent use it?",
    params=[
        param("query",  "What to search for"),                           # required string
        param("limit",  "Max results to return", type="integer", default=10),  # optional int
    ]
)
def myservice_search(query: str, limit: int = 10, _ctx: ToolContext = None) -> str:
    client  = _client(_ctx)
    results = client.get("/search", params={"q": query, "per_page": limit})

    items = results.get("items", [])
    if not items:
        return f"No results for '{query}'."

    lines = []
    for item in items:
        lines.append(f"• {item.get('name', '?')}  —  {item.get('url', '')}")
    return "\n".join(lines)


# ── Example: POST tool ────────────────────────────────────────────────────

@register_tool(
    description="Create a new item in MYSERVICE.",
    params=[
        param("title",       "Title of the item"),
        param("description", "Optional description", default=""),
        param("status",      "Item status", enum=["open", "closed", "draft"], default="open"),
    ]
)
def myservice_create(title: str, description: str = "", status: str = "open", _ctx: ToolContext = None) -> str:
    client = _client(_ctx)
    result = client.post("/items", json={
        "title":       title,
        "description": description,
        "status":      status,
    })

    item_id  = result.get("id", "?")
    item_url = result.get("url", "")
    return f"✓ Created '{title}'  (id: {item_id})\n  {item_url}"


# ── Example: File read tool (no HTTP) ────────────────────────────────────

@register_tool(
    description="Read a file from the bujji workspace and return its contents.",
    params=[
        param("filename", "Filename relative to the workspace, e.g. notes.md"),
    ]
)
def workspace_read(filename: str, _ctx: ToolContext = None) -> str:
    path = _ctx.workspace / filename
    if not path.exists():
        return f"File not found: {filename}"
    return path.read_text(encoding="utf-8")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  PARAM() QUICK REFERENCE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#
#  param("name", "desc")                          → required string
#  param("name", "desc", default="hello")         → optional string
#  param("name", "desc", type="integer")          → required int
#  param("name", "desc", type="integer", default=5) → optional int
#  param("name", "desc", type="boolean", default=False)
#  param("name", "desc", type="array",   default=[])
#  param("name", "desc", enum=["a","b","c"])      → string, only these values
#  param("name", "desc", enum=["a","b"], default="a")  → optional enum
#
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  HTTPCLIENT QUICK REFERENCE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#
#  client.get("/path")                            → GET /path
#  client.get("/path", params={"q": "search"})    → GET /path?q=search
#  client.post("/path", json={"key": "value"})    → POST with JSON body
#  client.patch("/path/id", json={"key": "val"})  → PATCH
#  client.put("/path/id",   json={"key": "val"})  → PUT
#  client.delete("/path/id")                      → DELETE
#
#  All methods return parsed JSON (dict/list) or raw text.
#  Non-2xx responses raise RuntimeError with a clean message.
#  ToolRegistry catches all exceptions — your tool never crashes bujji.
#
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  REAL-WORLD EXAMPLES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#
#  GitHub:
#    HttpClient(base_url="https://api.github.com",
#               headers={"Authorization": "token " + _ctx.cred("github.token"),
#                        "Accept": "application/vnd.github+json"})
#
#  OpenWeatherMap:
#    client.get("/weather", params={"q": city, "appid": _ctx.cred("openweather.api_key")})
#
#  Notion:
#    HttpClient(base_url="https://api.notion.com/v1",
#               headers={"Authorization": "Bearer " + _ctx.cred("notion.api_key"),
#                        "Notion-Version": "2022-06-28"})
#
#  Linear:
#    HttpClient(base_url="https://api.linear.app",
#               headers={"Authorization": _ctx.cred("linear.api_key")})
#
#  Telegram (send message):
#    bot_token = _ctx.cred("telegram.bot_token")
#    HttpClient(base_url=f"https://api.telegram.org/bot{bot_token}")
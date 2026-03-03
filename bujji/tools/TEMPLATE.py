"""
bujji/tools/TEMPLATE.py  —  copy-paste starting point for any new API tool

Steps:
  1. Copy this file to  bujji/tools/<yourservice>.py
  2. Fill in the service name, base URL, auth, and tools below
  3. Save — bujji hot-reloads it instantly, no restart needed

Credential storage
──────────────────
Credentials for your tool live in config.json under:

    {
      "tools": {
        "<yourservice>": {
          "api_key": "...",
          "other_key": "..."
        }
      }
    }

The user adds these in the web UI under Settings → Tools,
or you can tell them to add them to ~/.bujji/config.json directly.
"""

from bujji.tools.base import HttpClient, ToolContext, param, register_tool

# ── 1. Service name (used in cred() lookups and error messages) ──────────────
SERVICE = "myservice"   # → cfg["tools"]["myservice"]["api_key"]

# ── 2. Helper: build an authenticated client ─────────────────────────────────

def _client(_ctx: ToolContext) -> HttpClient:
    """
    Create an HttpClient for this API.
    _ctx.cred() returns the credential or raises a friendly error if it's missing.
    """
    return HttpClient(
        base_url = "https://api.myservice.com/v1",
        headers  = {
            "Authorization": "Bearer " + _ctx.cred(f"{SERVICE}.api_key"),
            "Content-Type":  "application/json",
        },
    )

# ─────────────────────────────────────────────────────────────────────────────
# ── 3. Tools — add as many as you need ───────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────

@register_tool(
    description="Search items in MyService.",
    params=[
        param("query",   "Search query"),
        param("limit",   "Max results to return", type="integer", default=10),
    ]
)
def myservice_search(query: str, limit: int = 10, _ctx: ToolContext = None) -> str:
    client = _client(_ctx)
    data   = client.get("/search", params={"q": query, "per_page": limit})
    items  = data.get("items", [])
    if not items:
        return f"No results for '{query}'."
    return "\n".join(f"- {item['name']}: {item.get('description', '')}" for item in items)


@register_tool(
    description="Create a new item in MyService.",
    params=[
        param("name",        "Item name"),
        param("description", "Item description",  required=False, default=""),
        param("tags",        "Tags for the item", type="array",   default=[]),
    ]
)
def myservice_create(name: str, description: str = "", tags: list = None, _ctx: ToolContext = None) -> str:
    client = _client(_ctx)
    result = client.post("/items", json={"name": name, "description": description, "tags": tags or []})
    return f"✓ Created item: {result.get('name')} (id={result.get('id')})"


# ─────────────────────────────────────────────────────────────────────────────
# REAL EXAMPLES — uncomment any block to use
# ─────────────────────────────────────────────────────────────────────────────

# ── Gmail (OAuth access token) ───────────────────────────────────────────────
#
# @register_tool(
#     description="Search emails in Gmail.",
#     params=[
#         param("query",       "Gmail search query, e.g. 'from:boss is:unread'"),
#         param("max_results", "Number of emails", type="integer", default=5),
#     ]
# )
# def gmail_search(query: str, max_results: int = 5, _ctx: ToolContext = None) -> str:
#     gmail = HttpClient(
#         base_url = "https://gmail.googleapis.com/gmail/v1/users/me",
#         headers  = {"Authorization": "Bearer " + _ctx.cred("gmail.access_token")},
#     )
#     resp  = gmail.get("/messages", params={"q": query, "maxResults": max_results})
#     msgs  = resp.get("messages", [])
#     if not msgs:
#         return "No emails found."
#     # Fetch each message summary
#     lines = []
#     for m in msgs[:max_results]:
#         detail = gmail.get(f"/messages/{m['id']}", params={"format": "metadata",
#                            "metadataHeaders": ["Subject", "From"]})
#         headers = {h["name"]: h["value"] for h in detail.get("payload", {}).get("headers", [])}
#         lines.append(f"• {headers.get('Subject','(no subject)')} — from {headers.get('From','?')}")
#     return "\n".join(lines)


# ── Notion ───────────────────────────────────────────────────────────────────
#
# @register_tool(
#     description="Search Notion pages and databases.",
#     params=[param("query", "Search query"), param("limit", "Max results", type="integer", default=5)]
# )
# def notion_search(query: str, limit: int = 5, _ctx: ToolContext = None) -> str:
#     notion = HttpClient(
#         base_url = "https://api.notion.com/v1",
#         headers  = {
#             "Authorization":  "Bearer " + _ctx.cred("notion.api_key"),
#             "Notion-Version": "2022-06-28",
#         },
#     )
#     data  = notion.post("/search", json={"query": query, "page_size": limit})
#     pages = data.get("results", [])
#     if not pages:
#         return f"No results for '{query}' in Notion."
#     lines = []
#     for p in pages:
#         props = p.get("properties", {})
#         title = next(
#             ("".join(t.get("plain_text","") for t in v.get("title", []))
#              for v in props.values() if v.get("type") == "title"),
#             p.get("id", "Untitled")
#         )
#         lines.append(f"• {title} → {p.get('url','')}")
#     return "\n".join(lines)


# ── Slack ────────────────────────────────────────────────────────────────────
#
# @register_tool(
#     description="Send a Slack message to a channel.",
#     params=[
#         param("channel", "Channel name like #general or a user ID"),
#         param("text",    "Message to send"),
#     ]
# )
# def slack_send(channel: str, text: str, _ctx: ToolContext = None) -> str:
#     slack  = HttpClient("https://slack.com/api",
#                          headers={"Authorization": "Bearer " + _ctx.cred("slack.bot_token")})
#     result = slack.post("/chat.postMessage", json={"channel": channel, "text": text})
#     if not result.get("ok"):
#         return f"[Slack] Error: {result.get('error', 'unknown')}"
#     return f"✓ Sent to {channel}"


# ── Airtable ─────────────────────────────────────────────────────────────────
#
# @register_tool(
#     description="List records from an Airtable table.",
#     params=[
#         param("table",      "Table name"),
#         param("filter",     "Filter formula, e.g. \"Status = 'Done'\"", required=False, default=""),
#         param("max_records","Max records to return", type="integer", default=20),
#     ]
# )
# def airtable_list(table: str, filter: str = "", max_records: int = 20, _ctx: ToolContext = None) -> str:
#     base_id = _ctx.cred("airtable.base_id")
#     airtable = HttpClient(
#         base_url = f"https://api.airtable.com/v0/{base_id}",
#         headers  = {"Authorization": "Bearer " + _ctx.cred("airtable.api_key")},
#     )
#     params = {"maxRecords": max_records}
#     if filter:
#         params["filterByFormula"] = filter
#     data    = airtable.get(f"/{table}", params=params)
#     records = data.get("records", [])
#     if not records:
#         return f"No records in {table}."
#     return "\n".join(str(r.get("fields", {})) for r in records)


# ── GitHub ───────────────────────────────────────────────────────────────────
#
# @register_tool(
#     description="List open issues in a GitHub repo.",
#     params=[
#         param("repo",  "owner/repo, e.g. 'torvalds/linux'"),
#         param("limit", "Max issues", type="integer", default=10),
#     ]
# )
# def github_issues(repo: str, limit: int = 10, _ctx: ToolContext = None) -> str:
#     gh     = HttpClient("https://api.github.com",
#                          headers={"Authorization": "Bearer " + _ctx.cred("github.token"),
#                                   "Accept": "application/vnd.github+json"})
#     issues = gh.get(f"/repos/{repo}/issues", params={"state": "open", "per_page": limit})
#     if not issues:
#         return f"No open issues in {repo}."
#     return "\n".join(f"#{i['number']} {i['title']} — {i['html_url']}" for i in issues
#                      if "pull_request" not in i)
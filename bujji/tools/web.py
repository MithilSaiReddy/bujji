"""
bujji/tools/web.py  —  v2
Brave Search API with a clear, actionable no-key message.
"""
from __future__ import annotations

from bujji.tools.base import ToolContext, register_tool

try:
    import requests as _requests
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False

@register_tool(
    description=(
        "Search the web for up-to-date information using Brave Search. "
        "Use whenever you need current facts, recent news, documentation, "
        "prices, or anything beyond your training data."
    ),
    parameters={
        "type":     "object",
        "required": ["query"],
        "properties": {
            "query": {
                "type":        "string",
                "description": "The search query.",
            },
            "max_results": {
                "type":        "integer",
                "description": "Number of results to return (default: 5, max: 20).",
            },
        },
    },
)
def web_search(query: str, max_results: int = None, _ctx: ToolContext = None) -> str:
    cfg     = _ctx.cfg if _ctx else {}
    api_key = (
        cfg.get("tools", {})
           .get("web", {})
           .get("search", {})
           .get("api_key", "")
    )
    if not max_results:
        max_results = (
            cfg.get("tools", {})
               .get("web", {})
               .get("search", {})
               .get("max_results", 5)
        )

    if not api_key:
        safe_q = query.replace(" ", "+")
        return (
            "[Web Search] Brave API key not configured.\n"
            "  → Get a free key (2,000 queries/month): https://brave.com/search/api\n"
            "  → Then run: python main.py onboard  (or add it in the web UI → Settings)\n"
            f"  → Manual search: https://search.brave.com/search?q={safe_q}"
        )

    if not _HAS_REQUESTS:
        return "[Web Search] requests not installed — run: pip install requests"

    headers = {
        "Accept":               "application/json",
        "Accept-Encoding":      "gzip",
        "X-Subscription-Token": api_key,
    }
    try:
        r = _requests.get(
            "https://api.search.brave.com/res/v1/web/search",
            headers=headers,
            params={"q": query, "count": min(int(max_results), 20)},
            timeout=10,
        )
        r.raise_for_status()
        results = r.json().get("web", {}).get("results", [])

        if not results:
            return f"No search results found for: {query}"

        lines = []
        for i, res in enumerate(results, 1):
            title = res.get("title", "(no title)")
            url   = res.get("url", "")
            desc  = res.get("description", "").strip()
            lines.append(f"{i}. {title}")
            lines.append(f"   {url}")
            if desc:
                lines.append(f"   {desc}")

        return "\n".join(lines)

    except _requests.exceptions.Timeout:
        return "[Web Search] Request timed out after 10s. Try a shorter query."
    except Exception as e:
        return f"[Web Search Error] {type(e).__name__}: {e}"

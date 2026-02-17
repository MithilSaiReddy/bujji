"""
bujji/tools/web.py
Web search tool using the Brave Search API.
"""

from bujji.tools.base import register_tool

try:
    import requests as _requests
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False


@register_tool(
    description=(
        "Search the web for up-to-date information using Brave Search. "
        "Use this whenever you need current facts, news, or any information "
        "that might be beyond your training data."
    ),
    parameters={
        "type": "object",
        "required": ["query"],
        "properties": {
            "query": {
                "type":        "string",
                "description": "The search query.",
            },
            "max_results": {
                "type":        "integer",
                "description": "Number of results to return (default 5, max 20).",
            },
        },
    },
)
def web_search(query: str, max_results: int = None, _ctx: dict = None) -> str:
    cfg     = _ctx["cfg"] if _ctx else {}
    api_key = cfg.get("tools", {}).get("web", {}).get("search", {}).get("api_key", "")
    if not max_results:
        max_results = cfg.get("tools", {}).get("web", {}).get("search", {}).get("max_results", 5)

    if not api_key:
        safe_q = query.replace(" ", "+")
        return (
            "[Web Search] No Brave API key configured.\n"
            f"Get a free key at https://brave.com/search/api\n"
            f"Manual search: https://search.brave.com/search?q={safe_q}"
        )

    if not _HAS_REQUESTS:
        return "requests not installed. Run: pip install requests"

    headers = {
        "Accept":              "application/json",
        "Accept-Encoding":     "gzip",
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
            return "No search results found."

        lines = []
        for i, res in enumerate(results, 1):
            lines.append(f"{i}. {res.get('title', '(no title)')}")
            lines.append(f"   URL: {res.get('url', '')}")
            desc = res.get("description", "").strip()
            if desc:
                lines.append(f"   {desc}")
        return "\n".join(lines)

    except Exception as e:
        return f"Search failed: {e}"
"""
bujji/tools/web.py  —  v3  (rewritten with new param() shorthand)
"""
from bujji.tools.base import HttpClient, ToolContext, param, register_tool


@register_tool(
    description=(
        "Search the web for up-to-date information using Brave Search. "
        "Use whenever you need current facts, recent news, documentation, "
        "prices, or anything beyond your training data."
    ),
    params=[
        param("query",       "The search query"),
        param("max_results", "Number of results (default 5, max 20)", type="integer", default=5),
    ]
)
def web_search(query: str, max_results: int = 5, _ctx: ToolContext = None) -> str:
    cfg     = _ctx.cfg if _ctx else {}
    api_key = _ctx.cred("web.api_key", required=False) if _ctx else ""

    if not api_key:
        safe_q = query.replace(" ", "+")
        return (
            "[Web Search] Brave API key not configured.\n"
            "  → Get a free key (2,000 queries/month): https://brave.com/search/api\n"
            "  → Add it in the web UI: Settings → Tools → Web Search\n"
            f"  → Manual search: https://search.brave.com/search?q={safe_q}"
        )

    brave  = HttpClient(
        base_url = "https://api.search.brave.com/res/v1",
        headers  = {
            "Accept":               "application/json",
            "Accept-Encoding":      "gzip",
            "X-Subscription-Token": api_key,
        },
    )

    try:
        data    = brave.get("/web/search", params={"q": query, "count": min(int(max_results), 20)})
        results = data.get("web", {}).get("results", [])
    except RuntimeError as e:
        return f"[Web Search Error] {e}"

    if not results:
        return f"No search results found for: {query}"

    lines = []
    for i, res in enumerate(results, 1):
        title = res.get("title", "(no title)")
        url   = res.get("url", "")
        desc  = res.get("description", "").strip()
        lines.append(f"{i}. {title}\n   {url}")
        if desc:
            lines.append(f"   {desc}")

    return "\n".join(lines)
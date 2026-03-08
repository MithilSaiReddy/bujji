"""
bujji/tools/web.py

Setup
─────
pip install ddgs
"""
from bujji.tools.base import ToolContext, param, register_tool


@register_tool(
    description=(
        "ALWAYS use this tool when the user asks about ANY current, recent, or "
        "real-world information — news, people, prices, weather, sports, politics, "
        "or ANYTHING that could have changed. You MUST call this tool instead of "
        "answering from memory. Do not say you cannot search."
    ),
    params=[
        param("query",       "The search query"),
        param("max_results", "Number of results (default 5, max 20)", type="integer", default=5),
    ]
)
def web_search(query: str, max_results: int = 5, _ctx: ToolContext = None) -> str:
    try:
        from ddgs import DDGS
    except ImportError:
        return (
            "[web_search] 'ddgs' is not installed.\n"
            "Run: pip install ddgs"
        )

    max_results = min(int(max_results), 20)

    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
    except Exception as e:
        return f"[Web Search Error] {e}"

    if not results:
        return f"No results found for: '{query}'"

    lines = []
    for i, r in enumerate(results, 1):
        title   = r.get("title", "(no title)")
        url     = r.get("href",  "")
        body = r.get("body", "")
        snippet = " ".join(body) if isinstance(body, list) else str(body).strip()

    return "\n\n".join(lines)
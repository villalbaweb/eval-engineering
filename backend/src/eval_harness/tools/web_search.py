from __future__ import annotations

import os

from langchain_core.tools import tool

from eval_harness.tools.base import register_tool


def _tavily(query: str, max_results: int) -> str:
    from langchain_tavily import TavilySearch

    res = TavilySearch(max_results=max_results).invoke({"query": query})
    items = res.get("results", []) if isinstance(res, dict) else []
    return "\n".join(f"- {r.get('title', '')} ({r.get('url', '')}): {str(r.get('content', ''))[:300]}"
                     for r in items) or "No results."


def _ddg(query: str, max_results: int) -> str:
    from duckduckgo_search import DDGS

    with DDGS() as d:
        items = list(d.text(query, max_results=max_results))
    return "\n".join(f"- {r.get('title', '')} ({r.get('href', '')}): {str(r.get('body', ''))[:300]}"
                     for r in items) or "No results."


@register_tool(cost_hint="medium", tags=("retrieval", "network"))
@tool
def web_search(query: str, max_results: int = 4) -> str:
    """Search the public web for current information. Returns title, URL and a snippet per result.
    Use for recent or external facts; use knowledge_base_search for evaluation-engineering concepts."""
    try:
        if os.environ.get("TAVILY_API_KEY"):
            return _tavily(query, max_results)
        return _ddg(query, max_results)
    except Exception as e:  # tools must return errors as text so the agent can recover
        return f"ERROR: web search failed ({type(e).__name__}: {e})"

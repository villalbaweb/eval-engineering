from __future__ import annotations

import httpx
from langchain_core.tools import tool
from markdownify import markdownify

from eval_harness.tools.base import register_tool

MAX_CHARS = 6000


@register_tool(cost_hint="medium", tags=("retrieval", "network"))
@tool
def fetch_url(url: str) -> str:
    """Download a web page (absolute http/https URL) and return it as markdown, truncated to
    about 6000 characters. Typically used after web_search to read a result."""
    if not url.startswith(("http://", "https://")):
        return "ERROR: url must be an absolute http(s) URL."
    try:
        r = httpx.get(url, timeout=15, follow_redirects=True, headers={"User-Agent": "eval-harness/0.1"})
        r.raise_for_status()
    except Exception as e:
        return f"ERROR: could not fetch {url} ({type(e).__name__}: {e})"
    text = markdownify(r.text, strip=["script", "style", "img"]).strip()
    return text[:MAX_CHARS] + ("\n...[truncated]" if len(text) > MAX_CHARS else "")

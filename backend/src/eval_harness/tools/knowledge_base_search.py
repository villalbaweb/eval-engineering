from __future__ import annotations

import re
from functools import lru_cache

from langchain_core.tools import tool
from rank_bm25 import BM25Okapi

from eval_harness.core.settings import get_settings
from eval_harness.tools.base import register_tool

STOP = {"the", "a", "an", "is", "are", "of", "to", "in", "on", "for", "and", "or", "what", "how", "does", "do",
        "according", "knowledge", "base", "using", "use", "me", "my", "i", "it", "that", "this", "with", "when",
        "explain", "tell", "about", "can", "should", "one", "per"}


def _tok(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9@^]+", text.lower()) if t not in STOP]


@lru_cache(maxsize=4)
def _index(corpus_dir: str):
    from pathlib import Path

    docs: list[tuple[str, str]] = []  # (doc_id, paragraph)
    for f in sorted(Path(corpus_dir).glob("*.md")):
        for para in re.split(r"\n\s*\n", f.read_text(encoding="utf-8")):
            if para.strip():
                docs.append((f.stem, para.strip()))
    titles = {stem: stem.replace("-", " ") for stem, _ in docs}
    if not docs:
        return None, []
    # the document title is indexed with every passage so short queries find the right file
    return BM25Okapi([_tok(titles[stem] + " " + p) for stem, p in docs]), docs


@register_tool(tags=("retrieval", "deterministic"))
@tool
def knowledge_base_search(query: str, top_k: int = 3) -> str:
    """Search the local evaluation-engineering knowledge base (BM25). Returns the best passages,
    each prefixed with its source document id in square brackets, e.g. [pass-at-k]. Cite those ids."""
    bm25, docs = _index(str(get_settings().corpus_dir))
    if bm25 is None:
        return "Knowledge base is empty."
    scores = bm25.get_scores(_tok(query))
    ranked = sorted(range(len(docs)), key=lambda i: scores[i], reverse=True)[: max(1, top_k)]
    hits = [i for i in ranked if scores[i] > 0]
    if not hits:
        return "No relevant passages found."
    return "\n\n".join(f"[{docs[i][0]}] {docs[i][1]}" for i in hits)

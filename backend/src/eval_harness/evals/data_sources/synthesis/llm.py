"""LLM access for synthesis, with a deterministic template fallback for the offline provider."""

from __future__ import annotations

from collections.abc import Callable

from eval_harness.llm.factory import make_chat_model
from eval_harness.llm.settings import resolve_role


def offline() -> bool:
    return resolve_role("synthesizer").provider == "fake"


def write(prompt: str, fallback: Callable[[], str], *, system: str = "You write realistic test inputs for evals.") -> str:
    """Ask the synthesizer model (defaults to the judge model) for ONE text; offline -> template."""
    if offline():
        return fallback()
    model = make_chat_model("synthesizer")
    out = model.invoke([("system", system), ("human", prompt)])
    text = str(out.content).strip().strip('"')
    return text or fallback()

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field


class ToolCallRecord(BaseModel):
    id: str = ""
    name: str
    args: dict[str, Any] = Field(default_factory=dict)
    result: str = ""
    error: bool = False
    latency_s: float = 0.0
    replayed: bool = False
    injected_fault: str | None = None


class Usage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float | None = None
    model_calls: int = 0


class Transcript(BaseModel):
    """Normalized record of one trial.

    ``messages`` use OpenAI chat format so they can be fed to agentevals / openevals
    and stored as plain JSON without LangChain types.
    """

    messages: list[dict[str, Any]] = Field(default_factory=list)
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    skills_loaded: list[str] = Field(default_factory=list)
    usage: Usage = Field(default_factory=Usage)
    latency_s: float = 0.0
    model_slug: str = ""
    trace_url: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)

    @property
    def final_answer(self) -> str:
        for m in reversed(self.messages):
            if m.get("role") == "assistant" and m.get("content") and not m.get("tool_calls"):
                return _text(m["content"])
        for m in reversed(self.messages):
            if m.get("role") == "assistant" and m.get("content"):
                return _text(m["content"])
        return ""

    @property
    def tool_names(self) -> list[str]:
        return [t.name for t in self.tool_calls]

    @property
    def n_steps(self) -> int:
        return sum(1 for m in self.messages if m.get("role") == "assistant")

    def tool_result_text(self) -> str:
        return "\n".join(t.result for t in self.tool_calls)


def _text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in content)
    return json.dumps(content)

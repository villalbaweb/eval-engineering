from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class Outcome(BaseModel):
    """The end result of a trial: the final answer plus execution status / side effects."""

    final_answer: str = ""
    status: Literal["ok", "error", "timeout", "step_limit"] = "ok"
    error: str | None = None
    state: dict[str, Any] = Field(default_factory=dict)

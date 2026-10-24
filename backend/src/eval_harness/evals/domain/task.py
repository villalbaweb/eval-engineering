from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ExpectedToolCall(BaseModel):
    name: str
    args: dict[str, Any] | None = None  # None = do not check arguments


class Expected(BaseModel):
    """Everything a grader may compare against. Each grader reads only its own fields."""

    skills_loaded: list[str] = Field(default_factory=list)
    forbidden_skills: list[str] = Field(default_factory=list)
    tool_calls: list[ExpectedToolCall] = Field(default_factory=list)
    forbidden_tools: list[str] = Field(default_factory=list)
    trajectory_mode: Literal["strict", "unordered", "subset", "superset"] = "superset"
    answer_contains: list[str] = Field(default_factory=list)
    answer_not_contains: list[str] = Field(default_factory=list)
    answer_regex: str | None = None
    reference_answer: str | None = None
    final_answer_criteria: list[str] = Field(default_factory=list)
    cited_sources: list[str] = Field(default_factory=list)
    max_steps: int | None = None
    should_refuse: bool | None = None


class TaskSetup(BaseModel):
    """Per-task environment: fault injection, replay cassette, simulated-user persona."""

    fault_profile: str | None = None
    cassette: str | None = None
    persona: str | None = None
    max_turns: int | None = None


class Task(BaseModel):
    id: str
    kind: Literal["capability", "regression"] = "regression"
    tags: list[str] = Field(default_factory=list)
    description: str = ""
    input: dict[str, Any]  # {"messages": [{"role": "user", "content": "..."}]}
    expected: Expected = Field(default_factory=Expected)
    graders: list[str] | None = None  # restrict to these grader names (None = suite default)
    setup: TaskSetup = Field(default_factory=TaskSetup)
    source: str = "manual"  # manual | synthetic:<generator> | traces:<adapter>
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def user_text(self) -> str:
        msgs = self.input.get("messages", [])
        users = [m["content"] for m in msgs if m.get("role") == "user"]
        return users[-1] if users else ""

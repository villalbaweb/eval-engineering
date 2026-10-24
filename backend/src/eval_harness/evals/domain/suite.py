from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class GraderSpec(BaseModel):
    """Reference to a registered grader type plus its configuration."""

    type: str
    name: str | None = None  # defaults to type; must be unique within the suite
    args: dict[str, Any] = Field(default_factory=dict)
    layer: int | None = None  # override: 1 code, 2 trajectory, 3 model
    when_tags: list[str] = Field(default_factory=list)  # run only for tasks having any of these tags

    @property
    def key(self) -> str:
        return self.name or self.type


class RunSettings(BaseModel):
    k: int = 1  # trials per task
    concurrency: int = 4
    timeout_s: float = 90.0
    tool_mode: Literal["live", "record", "replay"] = "live"
    fail_fast: bool = True  # skip costlier layers when a cheaper layer failed
    max_tasks: int | None = None
    seed: int | None = None


class Suite(BaseModel):
    name: str
    description: str = ""
    datasets: list[str]  # paths/globs relative to evals/datasets
    include_tags: list[str] = Field(default_factory=list)
    exclude_tags: list[str] = Field(default_factory=list)
    kinds: list[str] = Field(default_factory=list)
    graders: list[GraderSpec]
    run: RunSettings = Field(default_factory=RunSettings)
    agent: str = "copilot-baseline"  # name of an agent config in evals/agents
    target: str = "local_agent"

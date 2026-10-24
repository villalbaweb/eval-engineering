"""AgentConfig: the main experiment variable. Agents are YAML files in ``evals/agents``."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field

from eval_harness.core.settings import get_settings


class ModelOverride(BaseModel):
    """Optional per-agent model choice; omitted fields fall back to the .env settings."""

    provider: str | None = None
    name: str | None = None
    temperature: float | None = None


class MiddlewareRef(BaseModel):
    name: str
    args: dict[str, Any] = Field(default_factory=dict)


class AgentConfig(BaseModel):
    name: str
    description: str = ""
    model: ModelOverride = Field(default_factory=ModelOverride)
    prompt: str = "copilot_system.md"  # file in agent/prompts
    prompt_text: str | None = None  # inline prompt overrides the file
    tools: list[str] | Literal["all"] = "all"
    skills: list[str] | Literal["all", "none"] = "all"
    skill_loader_mode: Literal["per_skill", "generic"] = "per_skill"
    middleware: list[MiddlewareRef | str] = Field(default_factory=list)
    recursion_limit: int = 30

    def middleware_refs(self) -> list[MiddlewareRef]:
        return [MiddlewareRef(name=m) if isinstance(m, str) else m for m in self.middleware]


def agent_path(name: str) -> Path:
    return get_settings().agents_dir / f"{name}.yaml"


def load_agent_config(name: str) -> AgentConfig:
    p = agent_path(name)
    if not p.exists():
        available = sorted(x.stem for x in get_settings().agents_dir.glob("*.yaml"))
        raise FileNotFoundError(f"agent config '{name}' not found. Available: {available}")
    return AgentConfig.model_validate(yaml.safe_load(p.read_text(encoding="utf-8")))


def list_agent_configs() -> list[AgentConfig]:
    return [load_agent_config(p.stem) for p in sorted(get_settings().agents_dir.glob("*.yaml"))]

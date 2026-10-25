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


AGENT_TARGETS = ("local_agent", "multiturn_sim")  # variants whose config is an AgentConfig


def agent_path(name: str) -> Path:
    """Legacy layout: the agent config file (profiles layout: ``<profile>/variants/<name>.yaml``)."""
    return get_settings().agents_dir / f"{name}.yaml"


def config_from_variant(variant: Any, *, legacy_file: Path | None = None) -> AgentConfig:
    """AgentConfig of an in-process (``local_agent``) variant."""
    if legacy_file is not None:  # keep the file's own fields (incl. its ``name``) exactly as before
        return AgentConfig.model_validate(yaml.safe_load(legacy_file.read_text(encoding="utf-8")))
    return AgentConfig.model_validate({**variant.config, "name": variant.name, "description": variant.description})


def load_agent_config(name: str) -> AgentConfig:
    """Agent config by variant name, alias (e.g. ``copilot-baseline``) or ``profile:variant``,
    resolved in the active profile."""
    from eval_harness.profiles.loader import VariantNotFound, is_legacy_layout, resolve_variant

    if is_legacy_layout():
        p = agent_path(name)
        if not p.exists():
            available = sorted(x.stem for x in get_settings().agents_dir.glob("*.yaml"))
            raise FileNotFoundError(f"agent config '{name}' not found. Available: {available}")
        return config_from_variant(None, legacy_file=p)
    try:
        _, v = resolve_variant(name)
    except VariantNotFound as e:
        raise FileNotFoundError(f"agent config '{name}' not found ({e})") from e
    if v.target not in AGENT_TARGETS:
        raise FileNotFoundError(f"variant '{v.name}' uses target '{v.target}', not an in-process agent")
    return config_from_variant(v)


def list_agent_configs() -> list[AgentConfig]:
    """In-process agent variants of the active profile (the legacy ``evals/agents`` files)."""
    from eval_harness.profiles.loader import is_legacy_layout, list_variants

    if is_legacy_layout():
        return [load_agent_config(p.stem) for p in sorted(get_settings().agents_dir.glob("*.yaml"))]
    return [config_from_variant(v) for v in list_variants() if v.target in AGENT_TARGETS]

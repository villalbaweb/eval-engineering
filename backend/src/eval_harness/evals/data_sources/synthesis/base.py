"""Synthetic task generators (plug-ins).

Add a file here with a class decorated by ``@register_generator("name")``. Generators are
configured by YAML in ``evals/synthesis/`` and produce *candidate* tasks that go through the same
review queue as imported traces.
"""

from __future__ import annotations

import random
import re
from typing import Any, ClassVar

import yaml
from pydantic import BaseModel, Field

from eval_harness.core.registry import Registry
from eval_harness.core.settings import get_settings
from eval_harness.evals.domain.task import Expected, Task


class SynthesisConfig(BaseModel):
    name: str
    generator: str
    count: int = 10
    seed: int = 0
    kind: str = "capability"
    tags: list[str] = Field(default_factory=lambda: ["synthetic"])
    dimensions: dict[str, Any] = Field(default_factory=dict)  # dim -> [values] | {value: expected-fragment}
    options: dict[str, Any] = Field(default_factory=dict)  # generator-specific


class Generator:
    type: ClassVar[str] = ""
    description: ClassVar[str] = ""

    def __init__(self, cfg: SynthesisConfig):
        self.cfg = cfg
        self.rng = random.Random(cfg.seed)

    def generate(self) -> list[Task]:  # pragma: no cover - interface
        raise NotImplementedError

    def make_task(self, idx: int, text: str, expected: dict[str, Any] | None = None, *, extra_tags: list[str] | None = None,
                  metadata: dict[str, Any] | None = None, setup: dict[str, Any] | None = None) -> Task:
        return Task(
            id=f"syn-{self.cfg.name}-{idx:03d}", kind=self.cfg.kind,  # type: ignore[arg-type]
            tags=[*self.cfg.tags, *(extra_tags or [])],
            input={"messages": [{"role": "user", "content": text}]},
            expected=Expected.model_validate(expected or {}), source=f"synthetic:{self.type}",
            metadata=metadata or {}, setup=setup or {})


generator_registry: Registry[type[Generator]] = Registry(
    "generator", package="eval_harness.evals.data_sources.synthesis", entry_point_group="eval_harness.generators"
)


def register_generator(type_: str):
    def deco(cls: type[Generator]) -> type[Generator]:
        cls.type = type_
        generator_registry.register(type_)(cls)
        return cls

    return deco


def load_config(name: str) -> SynthesisConfig:
    p = get_settings().synthesis_dir / f"{name}.yaml"
    if not p.exists():
        raise FileNotFoundError(f"synthesis config '{name}' not found in {get_settings().synthesis_dir}")
    return SynthesisConfig.model_validate(yaml.safe_load(p.read_text(encoding="utf-8")))


def merge_expected(parts: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for p in parts:
        for k, v in p.items():
            out[k] = [*out.get(k, []), *v] if isinstance(v, list) and isinstance(out.get(k), list) else v
    return out


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:24]

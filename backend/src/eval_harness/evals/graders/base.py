"""Grader protocol, registry and the layered (fail-fast) pipeline.

A grader inspects a trial (the task's expectations + the transcript + the outcome) and returns a
:class:`GradeResult`. To add one: create a file under ``graders/code|model|human`` containing a
subclass decorated with ``@register_grader("my_type")``. Graders that have nothing to check for a
given task return ``GradeResult.skip(...)`` instead of a fake pass.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, ClassVar

from eval_harness.core.registry import Registry
from eval_harness.evals.domain.grade import GradeResult
from eval_harness.evals.domain.outcome import Outcome
from eval_harness.evals.domain.profile import Conventions, Profile
from eval_harness.evals.domain.suite import GraderSpec
from eval_harness.evals.domain.task import Task
from eval_harness.evals.domain.transcript import Transcript


@dataclass
class GradeContext:
    task: Task
    transcript: Transcript
    outcome: Outcome
    trial_id: str = ""
    experiment_id: str = ""
    profile: Profile | None = None  # the agent under test (read-only); None = the lab's own conventions

    @property
    def conventions(self) -> Conventions:
        """How to read this agent's transcripts (skills, tool errors, citations)."""
        return self.profile.conventions if self.profile is not None else Conventions()


class Grader:
    type: ClassVar[str] = ""
    layer: ClassVar[int] = 1  # 1 code (cheap) -> 2 trajectory -> 3 model (expensive)
    description: ClassVar[str] = ""

    def __init__(self, name: str | None = None, **args: Any):
        self.name = name or self.type
        self.args = args
        self.when_tags: list[str] = []

    def grade(self, ctx: GradeContext) -> GradeResult:  # pragma: no cover - interface
        raise NotImplementedError

    async def agrade(self, ctx: GradeContext) -> GradeResult:
        return await asyncio.to_thread(self.grade, ctx)

    # helpers --------------------------------------------------------
    def passed(self, ok: bool, why: str = "", **details: Any) -> GradeResult:
        return GradeResult.of(self.name, ok, why, layer=self.layer, **details)

    def skip(self, why: str) -> GradeResult:
        return GradeResult.skip(self.name, why, self.layer)


grader_registry: Registry[type[Grader]] = Registry(
    "grader", package="eval_harness.evals.graders", entry_point_group="eval_harness.graders"
)


def register_grader(type_: str):
    def deco(cls: type[Grader]) -> type[Grader]:
        cls.type = type_
        grader_registry.register(type_)(cls)
        return cls

    return deco


def build_grader(spec: GraderSpec) -> Grader:
    cls = grader_registry.get(spec.type)
    g = cls(name=spec.key, **spec.args)
    if spec.layer is not None:
        g.layer = spec.layer  # instance override
    g.when_tags = list(spec.when_tags)
    return g


class GraderPipeline:
    """Runs graders layer by layer; when ``fail_fast`` a failure in a cheaper layer skips the
    more expensive layers (so LLM judges only run when basic structural checks pass)."""

    def __init__(self, specs: list[GraderSpec], *, fail_fast: bool = True):
        self.graders = [build_grader(s) for s in specs]
        self.fail_fast = fail_fast

    def select(self, task: Task) -> list[Grader]:
        chosen = self.graders if task.graders is None else [g for g in self.graders if g.name in task.graders]
        return [g for g in chosen if not g.when_tags or set(g.when_tags) & set(task.tags)]

    async def run(self, ctx: GradeContext) -> list[GradeResult]:
        results: list[GradeResult] = []
        graders = self.select(ctx.task)
        for layer in sorted({g.layer for g in graders}):
            group = [g for g in graders if g.layer == layer]
            blocked = self.fail_fast and any(r.passed is False for r in results)
            if blocked:
                results += [GradeResult.skip(g.name, "skipped: a cheaper grader layer already failed", layer)
                            for g in group]
                continue
            outs = await asyncio.gather(*(self._safe(g, ctx) for g in group))
            results += list(outs)
        return results

    @staticmethod
    async def _safe(g: Grader, ctx: GradeContext) -> GradeResult:
        try:
            r = await g.agrade(ctx)
        except Exception as e:  # noqa: BLE001 - a broken grader must not kill the experiment
            return GradeResult(grader=g.name, layer=g.layer, skipped=True,
                               rationale=f"grader error: {type(e).__name__}: {e}")
        r.layer = g.layer
        return r

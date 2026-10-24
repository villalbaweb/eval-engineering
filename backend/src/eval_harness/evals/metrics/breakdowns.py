from __future__ import annotations

from collections import defaultdict
from typing import Any

from eval_harness.evals.domain.task import Task
from eval_harness.evals.domain.trial import Trial
from eval_harness.evals.metrics.registry import metric_registry


def _rate(flags: list[bool]) -> dict[str, Any]:
    return {"n": len(flags), "pass_rate": (sum(flags) / len(flags)) if flags else 0.0}


@metric_registry.register("by_tag")
def by_tag(trials: list[Trial], tasks: dict[str, Task], k: int) -> dict[str, Any]:
    acc: dict[str, list[bool]] = defaultdict(list)
    for t in trials:
        for tag in tasks[t.task_id].tags if t.task_id in tasks else []:
            acc[tag].append(t.passed)
    return {tag: _rate(v) for tag, v in sorted(acc.items())}


@metric_registry.register("by_kind")
def by_kind(trials: list[Trial], tasks: dict[str, Task], k: int) -> dict[str, Any]:
    acc: dict[str, list[bool]] = defaultdict(list)
    for t in trials:
        if t.task_id in tasks:
            acc[tasks[t.task_id].kind].append(t.passed)
    return {kind: _rate(v) for kind, v in sorted(acc.items())}


@metric_registry.register("by_source")
def by_source(trials: list[Trial], tasks: dict[str, Task], k: int) -> dict[str, Any]:
    acc: dict[str, list[bool]] = defaultdict(list)
    for t in trials:
        if t.task_id in tasks:
            acc[tasks[t.task_id].source.split(":")[0]].append(t.passed)
    return {src: _rate(v) for src, v in sorted(acc.items())}


@metric_registry.register("by_grader")
def by_grader(trials: list[Trial], tasks: dict[str, Task], k: int) -> dict[str, Any]:
    acc: dict[str, list[bool]] = defaultdict(list)
    skipped: dict[str, int] = defaultdict(int)
    for t in trials:
        for g in t.grades:
            if g.skipped:
                skipped[g.grader] += 1
            else:
                acc[g.grader].append(bool(g.passed))
    out = {name: _rate(v) for name, v in sorted(acc.items())}
    for name, s in skipped.items():
        out.setdefault(name, {"n": 0, "pass_rate": 0.0})["skipped"] = s
    return out

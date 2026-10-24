"""Metric plug-in registry.

A metric is ``fn(trials, tasks, k) -> dict`` where ``trials`` is a list of graded
:class:`Trial`, ``tasks`` maps task id -> :class:`Task`, and ``k`` is the trials-per-task
setting. Add a file in this package decorated with ``@metric_registry.register("name")``
and it appears in every experiment summary.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from eval_harness.core.registry import Registry
from eval_harness.evals.domain.task import Task
from eval_harness.evals.domain.trial import Trial

MetricFn = Callable[[list[Trial], dict[str, Task], int], dict[str, Any]]

metric_registry: Registry[MetricFn] = Registry(
    "metric", package="eval_harness.evals.metrics", entry_point_group="eval_harness.metrics"
)


def summarize(trials: list[Trial], tasks: dict[str, Task], k: int) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name, fn in metric_registry.items():
        out[name] = fn(trials, tasks, k)
    return out

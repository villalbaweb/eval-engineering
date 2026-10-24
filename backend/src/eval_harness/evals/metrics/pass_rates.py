from __future__ import annotations

from collections import defaultdict
from typing import Any

from eval_harness.evals.domain.task import Task
from eval_harness.evals.domain.trial import Trial
from eval_harness.evals.metrics import core
from eval_harness.evals.metrics.registry import metric_registry


def per_task_counts(trials: list[Trial]) -> dict[str, tuple[int, int]]:
    """task_id -> (n_trials, n_passed)."""
    acc: dict[str, list[bool]] = defaultdict(list)
    for t in trials:
        acc[t.task_id].append(t.passed)
    return {tid: (len(v), sum(v)) for tid, v in acc.items()}


@metric_registry.register("pass_rates")
def pass_rates(trials: list[Trial], tasks: dict[str, Task], k: int) -> dict[str, Any]:
    counts = per_task_counts(trials)
    per_task = {}
    for tid, (n, c) in counts.items():
        kk = min(max(k, 1), n)
        per_task[tid] = {
            "n": n, "passed": c, "pass_rate": c / n,
            "pass_at_k": core.pass_at_k(n, c, kk),
            "pass_pow_k": core.pass_pow_k(n, c, kk),
        }
    flags = [1.0 if t.passed else 0.0 for t in trials]
    m, lo, hi = core.bootstrap_ci(flags)
    task_rates = [v["pass_rate"] for v in per_task.values()]
    return {
        "k": k,
        "n_trials": len(trials),
        "n_tasks": len(per_task),
        "trial_pass_rate": m,
        "ci95": [lo, hi],
        "mean_pass_at_k": core.mean([v["pass_at_k"] for v in per_task.values()]),
        "mean_pass_pow_k": core.mean([v["pass_pow_k"] for v in per_task.values()]),
        "task_pass_rate": core.mean(task_rates),
        "per_task": per_task,
    }

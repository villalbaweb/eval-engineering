from __future__ import annotations

from typing import Any

from eval_harness.evals.domain.task import Task
from eval_harness.evals.domain.trial import Trial
from eval_harness.evals.metrics.pass_rates import per_task_counts
from eval_harness.evals.metrics.registry import metric_registry


@metric_registry.register("flakiness")
def flakiness(trials: list[Trial], tasks: dict[str, Task], k: int) -> dict[str, Any]:
    """Split tasks into reliable / flaky (0 < c < n) / systematic failures (c = 0).

    With k >= 3 this separates prompt/tool bugs (0/k) from non-determinism (some pass).
    """
    reliable, flaky, systematic = [], [], []
    for tid, (n, c) in per_task_counts(trials).items():
        (reliable if c == n else systematic if c == 0 else flaky).append(tid)
    return {"reliable": sorted(reliable), "flaky": sorted(flaky), "systematic": sorted(systematic),
            "informative": k >= 3}

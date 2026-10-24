from __future__ import annotations

from typing import Any

from eval_harness.evals.domain.task import Task
from eval_harness.evals.domain.trial import Trial
from eval_harness.evals.metrics import core
from eval_harness.evals.metrics.registry import metric_registry


@metric_registry.register("cost_latency")
def cost_latency(trials: list[Trial], tasks: dict[str, Task], k: int) -> dict[str, Any]:
    lat = [t.transcript.latency_s or t.duration_s for t in trials]
    tokens = [t.transcript.usage.total_tokens for t in trials]
    costs = [t.transcript.usage.cost_usd for t in trials if t.transcript.usage.cost_usd is not None]
    steps = [t.transcript.n_steps for t in trials]
    tool_calls = [len(t.transcript.tool_calls) for t in trials]
    return {
        "latency_p50_s": core.percentile(lat, 0.5),
        "latency_p95_s": core.percentile(lat, 0.95),
        "tokens_mean": core.mean(tokens),
        "tokens_total": sum(tokens),
        "cost_total_usd": sum(costs) if costs else None,
        "steps_mean": core.mean(steps),
        "tool_calls_mean": core.mean(tool_calls),
        "errors": sum(1 for t in trials if t.outcome.status != "ok"),
    }

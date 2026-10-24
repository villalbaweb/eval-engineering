"""Efficiency and resource graders: steps, loops, tokens, latency."""

from __future__ import annotations

from collections import Counter

from eval_harness.evals.domain.grade import GradeResult
from eval_harness.evals.graders.base import GradeContext, Grader, register_grader


@register_grader("step_efficiency")
class StepEfficiency(Grader):
    """Fails on repeated identical tool calls (loops) or too many steps.
    Step limit: ``expected.max_steps`` else ``args.max_steps`` (default 12)."""

    layer = 2
    description = "No identical repeated tool calls and steps within the limit."

    def grade(self, ctx: GradeContext) -> GradeResult:
        limit = ctx.task.expected.max_steps or int(self.args.get("max_steps", 12))
        calls = Counter((c.name, str(sorted(c.args.items()))) for c in ctx.transcript.tool_calls)
        repeats = {f"{n}{a}": c for (n, a), c in calls.items() if c > 1}
        steps = ctx.transcript.n_steps
        ok = steps <= limit and not repeats
        why = []
        if steps > limit:
            why.append(f"{steps} steps > limit {limit}")
        if repeats:
            why.append(f"repeated calls: {repeats}")
        return GradeResult.of(self.name, ok, "; ".join(why) or f"{steps} steps, no loops", layer=self.layer,
                              score=max(0.0, 1 - max(0, steps - limit) / max(limit, 1)), steps=steps)


@register_grader("budget")
class Budget(Grader):
    """Resource budget. args: max_tokens, max_latency_s, max_cost_usd, max_tool_calls."""

    description = "Token / latency / cost / tool-call budget."

    def grade(self, ctx: GradeContext) -> GradeResult:
        t, a = ctx.transcript, self.args
        breaches = []
        if "max_tokens" in a and t.usage.total_tokens > a["max_tokens"]:
            breaches.append(f"tokens {t.usage.total_tokens} > {a['max_tokens']}")
        if "max_latency_s" in a and t.latency_s > a["max_latency_s"]:
            breaches.append(f"latency {t.latency_s:.1f}s > {a['max_latency_s']}s")
        if "max_cost_usd" in a and (t.usage.cost_usd or 0) > a["max_cost_usd"]:
            breaches.append(f"cost ${t.usage.cost_usd:.4f} > ${a['max_cost_usd']}")
        if "max_tool_calls" in a and len(t.tool_calls) > a["max_tool_calls"]:
            breaches.append(f"tool calls {len(t.tool_calls)} > {a['max_tool_calls']}")
        return self.passed(not breaches, "; ".join(breaches) or "within budget", breaches=breaches)

"""Trajectory graders (layer 2): the path the agent took, not only its answer."""

from __future__ import annotations

import json

from agentevals.trajectory.match import create_trajectory_match_evaluator

from eval_harness.evals.domain.grade import GradeResult
from eval_harness.evals.domain.task import Task
from eval_harness.evals.graders.base import GradeContext, Grader, register_grader


def reference_trajectory(task: Task) -> list[dict]:
    """Build an OpenAI-format reference trajectory from ``expected.tool_calls``."""
    msgs: list[dict] = list(task.input.get("messages", []))
    for i, tc in enumerate(task.expected.tool_calls):
        cid = f"ref_{i}"
        msgs.append({"role": "assistant", "content": "", "tool_calls": [
            {"id": cid, "type": "function", "function": {"name": tc.name, "arguments": json.dumps(tc.args or {})}}]})
        msgs.append({"role": "tool", "tool_call_id": cid, "content": ""})
    msgs.append({"role": "assistant", "content": "(final answer)"})
    return msgs


@register_grader("trajectory_match")
class TrajectoryMatch(Grader):
    """agentevals trajectory match. Mode comes from ``expected.trajectory_mode``
    (strict | unordered | subset | superset); override with ``args.mode``. Tool arguments are only
    compared for expected calls that specify ``args``."""

    layer = 2
    description = "Compare actual tool calls with expected.tool_calls using agentevals (4 match modes)."

    def grade(self, ctx: GradeContext) -> GradeResult:
        if not ctx.task.expected.tool_calls:
            return self.skip("task has no expected.tool_calls")
        mode = self.args.get("mode") or ctx.task.expected.trajectory_mode
        overrides = {tc.name: "ignore" for tc in ctx.task.expected.tool_calls if tc.args is None}
        any_args = any(tc.args is not None for tc in ctx.task.expected.tool_calls)
        ev = create_trajectory_match_evaluator(
            trajectory_match_mode=mode,
            tool_args_match_mode="exact" if any_args else "ignore",
            tool_args_match_overrides=overrides or None,
        )
        res = ev(outputs=ctx.transcript.messages, reference_outputs=reference_trajectory(ctx.task))
        ok = bool(res.get("score"))
        return self.passed(ok, f"{mode} match: {'yes' if ok else 'no'}", mode=mode,
                           actual=ctx.transcript.tool_names,
                           expected=[t.name for t in ctx.task.expected.tool_calls])


@register_grader("trajectory_subsequence")
class TrajectorySubsequence(Grader):
    """Partial credit: fraction of expected tool calls that appear *in order* in the actual run.
    Passes when the fraction >= args.threshold (default 1.0)."""

    layer = 2
    description = "In-order subsequence score of expected tool calls (0..1) with partial credit."

    def grade(self, ctx: GradeContext) -> GradeResult:
        expected = [t.name for t in ctx.task.expected.tool_calls]
        if not expected:
            return self.skip("task has no expected.tool_calls")
        i = 0
        for name in ctx.transcript.tool_names:
            if i < len(expected) and name == expected[i]:
                i += 1
        score = i / len(expected)
        thr = float(self.args.get("threshold", 1.0))
        return GradeResult.of(self.name, score >= thr, f"{i}/{len(expected)} expected steps in order",
                              layer=self.layer, score=score, actual=ctx.transcript.tool_names, expected=expected)

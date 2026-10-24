"""Tool-use assertions on the transcript."""

from __future__ import annotations

from eval_harness.evals.domain.grade import GradeResult
from eval_harness.evals.graders.base import GradeContext, Grader, register_grader


def _args_subset(expected: dict, actual: dict) -> bool:
    return all(k in actual and actual[k] == v for k, v in expected.items())


@register_grader("tool_called")
class ToolCalled(Grader):
    description = "Every tool in expected.tool_calls was called (and its args match when specified)."

    def grade(self, ctx: GradeContext) -> GradeResult:
        exp = ctx.task.expected.tool_calls
        if not exp:
            return self.skip("task has no expected.tool_calls")
        missing = []
        for e in exp:
            calls = [c for c in ctx.transcript.tool_calls if c.name == e.name]
            if not calls or (e.args is not None and not any(_args_subset(e.args, c.args) for c in calls)):
                missing.append(e.name)
        return self.passed(not missing, f"expected tool calls missing/mismatched: {missing}" if missing
                           else "all expected tools called", missing=missing,
                           called=ctx.transcript.tool_names)


@register_grader("tool_not_called")
class ToolNotCalled(Grader):
    description = "None of expected.forbidden_tools was called."

    def grade(self, ctx: GradeContext) -> GradeResult:
        forbidden = ctx.task.expected.forbidden_tools
        if not forbidden:
            return self.skip("task has no expected.forbidden_tools")
        hit = sorted({n for n in ctx.transcript.tool_names if n in forbidden})
        return self.passed(not hit, f"forbidden tools called: {hit}" if hit else "no forbidden tools called", hit=hit)


@register_grader("tool_errors")
class ToolErrors(Grader):
    description = "No tool call ended in an error (args: max_errors, default 0)."

    def grade(self, ctx: GradeContext) -> GradeResult:
        errs = [c for c in ctx.transcript.tool_calls if c.error and not c.injected_fault]
        mx = int(self.args.get("max_errors", 0))
        return self.passed(len(errs) <= mx, f"{len(errs)} unexpected tool errors", errors=[c.name for c in errs])

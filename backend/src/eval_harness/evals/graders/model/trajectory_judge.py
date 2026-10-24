from __future__ import annotations

from agentevals.trajectory.llm import (
    TRAJECTORY_ACCURACY_PROMPT,
    TRAJECTORY_ACCURACY_PROMPT_WITH_REFERENCE,
    create_trajectory_llm_as_judge,
)

from eval_harness.evals.domain.grade import GradeResult
from eval_harness.evals.graders.base import GradeContext, register_grader
from eval_harness.evals.graders.code.trajectory_match import reference_trajectory
from eval_harness.evals.graders.model.judge_base import JudgeGrader, get_judge, verdict


@register_grader("trajectory_judge")
class TrajectoryJudge(JudgeGrader):
    """agentevals LLM judge over the whole trajectory (with the expected tool calls as reference
    when the task has them)."""

    description = "LLM judge of trajectory quality (logic, progression, efficiency)."

    def judge_call(self, ctx: GradeContext) -> GradeResult:
        if not ctx.transcript.tool_calls:
            return self.skip("no tool calls to judge")
        with_ref = bool(ctx.task.expected.tool_calls)
        ev = create_trajectory_llm_as_judge(
            prompt=TRAJECTORY_ACCURACY_PROMPT_WITH_REFERENCE if with_ref else TRAJECTORY_ACCURACY_PROMPT,
            judge=get_judge(), feedback_key=self.name)
        res = ev(outputs=ctx.transcript.messages,
                 reference_outputs=reference_trajectory(ctx.task) if with_ref else None)
        ok, score, comment = verdict(res)
        return GradeResult(grader=self.name, layer=self.layer, passed=ok, score=score, rationale=comment,
                           details={"with_reference": with_ref})

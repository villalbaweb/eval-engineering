from __future__ import annotations

from openevals.llm import create_llm_as_judge

from eval_harness.evals.domain.grade import GradeResult
from eval_harness.evals.graders.base import GradeContext, register_grader
from eval_harness.evals.graders.model.judge_base import JudgeGrader, get_judge, load_rubric, verdict


@register_grader("llm_judge")
class LLMJudge(JudgeGrader):
    """Rubric-driven LLM judge (openevals). args:
      rubric: name of a file in evals/rubrics (default 'correctness')
      requires: list of task fields needed to run, e.g. ['final_answer_criteria'] (skip otherwise)
    Placeholders available in rubrics: {inputs} {outputs} {reference_outputs} {criteria} {tool_results}.
    """

    description = "Binary LLM-as-judge verdict from a rubric file (separate judge model)."

    def _vars(self, ctx: GradeContext) -> dict:
        e = ctx.task.expected
        return {
            "inputs": ctx.task.user_text,
            "outputs": ctx.transcript.final_answer or "(empty answer)",
            "reference_outputs": e.reference_answer or "(none)",
            "criteria": "\n".join(f"- {c}" for c in e.final_answer_criteria) or "(none)",
            "tool_results": ctx.transcript.tool_result_text() or "(no tool results)",
        }

    def judge_call(self, ctx: GradeContext) -> GradeResult:
        rubric_name = self.args.get("rubric", "correctness")
        needs = self.args.get("requires", [])
        if "final_answer_criteria" in needs and not ctx.task.expected.final_answer_criteria:
            return self.skip("task has no expected.final_answer_criteria")
        rubric = load_rubric(rubric_name)
        judge = get_judge()
        ev = create_llm_as_judge(prompt=rubric, judge=judge, feedback_key=self.name, use_reasoning=True)
        res = ev(**self._vars(ctx))
        ok, score, comment = verdict(res)
        return GradeResult(grader=self.name, layer=self.layer, passed=ok, score=score, rationale=comment,
                           details={"rubric": rubric_name})


@register_grader("groundedness")
class Groundedness(LLMJudge):
    """Is the answer supported by the tool results? Skipped when no tools were used."""

    description = "LLM judge: claims in the answer are supported by the tool results."

    def judge_call(self, ctx: GradeContext) -> GradeResult:
        if not ctx.transcript.tool_calls:
            return self.skip("no tool results to ground against")
        self.args = {**self.args, "rubric": self.args.get("rubric", "groundedness")}
        return super().judge_call(ctx)

from __future__ import annotations

from openevals.llm import create_llm_as_judge

from eval_harness.evals.domain.grade import GradeResult
from eval_harness.evals.graders.base import GradeContext, register_grader
from eval_harness.evals.graders.model.judge_base import JudgeGrader, get_judge, load_rubric, verdict


@register_grader("pairwise_judge")
class PairwiseJudge(JudgeGrader):
    """Agent answer vs expected.reference_answer, judged pairwise.

    args.swap (default true): also run with the order swapped. Results:
      win          - preferred in both orders
      loss         - dispreferred in both orders
      inconsistent - the judge just prefers whichever is first (position bias) -> counted as a tie
    Passes unless the agent loses. Run once with swap=false to *see* position bias (experiment E7).
    """

    description = "Pairwise preference vs reference answer with optional order swap (position-bias control)."

    def _a_better(self, judge, rubric: str, user: str, a: str, b: str) -> bool:
        ev = create_llm_as_judge(prompt=rubric, judge=judge, feedback_key="pairwise", use_reasoning=True)
        return verdict(ev(inputs=user, response_a=a, response_b=b, outputs=""))[0]

    def judge_call(self, ctx: GradeContext) -> GradeResult:
        ref = ctx.task.expected.reference_answer
        if not ref:
            return self.skip("task has no expected.reference_answer")
        rubric, judge = load_rubric(self.args.get("rubric", "pairwise")), get_judge()
        ans, user = ctx.transcript.final_answer or "(empty answer)", ctx.task.user_text
        first = self._a_better(judge, rubric, user, ans, ref)  # agent shown as A
        if not self.args.get("swap", True):
            return GradeResult(grader=self.name, layer=self.layer, passed=first, score=1.0 if first else 0.0,
                               rationale="agent preferred (single order, position bias not controlled)" if first
                               else "reference preferred (single order)", details={"swapped": False})
        second = self._a_better(judge, rubric, user, ref, ans)  # agent shown as B
        outcome = "win" if first and not second else "loss" if (not first) and second else "inconsistent"
        score = {"win": 1.0, "inconsistent": 0.5, "loss": 0.0}[outcome]
        return GradeResult(grader=self.name, layer=self.layer, passed=outcome != "loss", score=score,
                           rationale=f"pairwise outcome: {outcome}",
                           details={"outcome": outcome, "agent_as_a": first, "agent_as_b": not second,
                                    "position_bias": outcome == "inconsistent"})

from __future__ import annotations

from openevals.llm import create_llm_as_judge

from eval_harness.evals.domain.grade import GradeResult
from eval_harness.evals.graders.base import GradeContext, register_grader
from eval_harness.evals.graders.model.judge_base import JudgeGrader, get_judge, load_rubric, verdict
from eval_harness.evals.graders.model.llm_judge import LLMJudge


@register_grader("judge_ensemble")
class JudgeEnsemble(JudgeGrader):
    """Majority vote across several judge models (judge-variance experiments).

    args: models: ['provider:model', ...]  (default: the single configured judge twice at the
    judge temperature, which only measures sampling noise), rubric: rubric name.
    The vote split is stored in details so judge disagreement is visible.
    """

    description = "Majority vote of several judge models; reports agreement."

    def judge_call(self, ctx: GradeContext) -> GradeResult:
        models = self.args.get("models") or [None, None, None]
        rubric = load_rubric(self.args.get("rubric", "correctness"))
        vars_ = LLMJudge._vars(self, ctx)
        votes, comments = [], []
        for m in models:
            ev = create_llm_as_judge(prompt=rubric, judge=get_judge(m), feedback_key=self.name, use_reasoning=True)
            ok, _, comment = verdict(ev(**vars_))
            votes.append(ok)
            comments.append(f"{m or 'judge'}: {'pass' if ok else 'fail'} - {comment[:120]}")
        yes = sum(votes)
        passed = yes * 2 > len(votes)
        return GradeResult(grader=self.name, layer=self.layer, passed=passed, score=yes / len(votes),
                           rationale=f"{yes}/{len(votes)} judges passed",
                           details={"votes": votes, "unanimous": yes in (0, len(votes)), "comments": comments})

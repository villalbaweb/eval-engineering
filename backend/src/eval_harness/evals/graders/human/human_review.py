from __future__ import annotations

from eval_harness.evals.domain.grade import GradeResult
from eval_harness.evals.graders.base import GradeContext, Grader, register_grader
from eval_harness.storage.repositories import annotations


@register_grader("human_review")
class HumanReview(Grader):
    """Uses the human thumbs up/down given in the Annotate view; skipped until labelled.
    These labels are the ground truth used to calibrate every other grader."""

    layer = 3
    description = "Human label (thumbs) for the trial; skipped until annotated."

    def grade(self, ctx: GradeContext) -> GradeResult:
        row = next((a for a in annotations.all(ctx.experiment_id) if a.trial_id == ctx.trial_id), None)
        if row is None:
            return self.skip("not annotated yet")
        return GradeResult(grader=self.name, layer=self.layer, passed=row.good, score=1.0 if row.good else 0.0,
                           rationale=row.note, label=row.failure_tags or None)

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from eval_harness.core.ids import utcnow
from eval_harness.evals.domain.grade import GradeResult
from eval_harness.evals.domain.outcome import Outcome
from eval_harness.evals.domain.transcript import Transcript


class Trial(BaseModel):
    id: str
    experiment_id: str
    task_id: str
    index: int  # attempt i of k
    transcript: Transcript = Field(default_factory=Transcript)
    outcome: Outcome = Field(default_factory=Outcome)
    grades: list[GradeResult] = Field(default_factory=list)
    started_at: datetime = Field(default_factory=utcnow)
    duration_s: float = 0.0

    @property
    def passed(self) -> bool:
        """A trial passes when it did not error and every non-skipped grader passed."""
        if self.outcome.status != "ok":
            return False
        graded = [g for g in self.grades if not g.skipped]
        return bool(graded) and all(g.passed for g in graded)

    def grade(self, name: str) -> GradeResult | None:
        return next((g for g in self.grades if g.grader == name), None)

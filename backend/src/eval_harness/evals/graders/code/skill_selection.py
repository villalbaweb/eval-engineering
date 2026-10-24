from __future__ import annotations

from eval_harness.evals.domain.grade import GradeResult
from eval_harness.evals.graders.base import GradeContext, Grader, register_grader


@register_grader("skill_selection")
class SkillSelection(Grader):
    """Did the agent load the right skills (recall) and only those (precision)?

    Fails when a required skill is missing or a forbidden skill was loaded. With
    ``args.strict_precision: true`` loading any unexpected skill also fails.
    Score = F1 of loaded vs expected skills.
    """

    description = "Precision/recall of skills loaded against expected.skills_loaded / forbidden_skills."

    def grade(self, ctx: GradeContext) -> GradeResult:
        e = ctx.task.expected
        if not e.skills_loaded and not e.forbidden_skills:
            return self.skip("task has no expected.skills_loaded / forbidden_skills")
        loaded, want = set(ctx.transcript.skills_loaded), set(e.skills_loaded)
        missing, extra = sorted(want - loaded), sorted(loaded - want)
        forbidden_hit = sorted(loaded & set(e.forbidden_skills))
        tp = len(want & loaded)
        precision = tp / len(loaded) if loaded else (1.0 if not want else 0.0)
        recall = tp / len(want) if want else 1.0
        f1 = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
        ok = not missing and not forbidden_hit and not (self.args.get("strict_precision") and extra)
        why = []
        if missing:
            why.append(f"missing skills: {missing}")
        if forbidden_hit:
            why.append(f"forbidden skills loaded: {forbidden_hit}")
        if extra and not forbidden_hit:
            why.append(f"extra skills loaded: {extra}")
        return GradeResult.of(self.name, ok, "; ".join(why) or "skills as expected", layer=self.layer, score=f1,
                              loaded=sorted(loaded), missing=missing, extra=extra, precision=precision, recall=recall)

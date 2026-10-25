from __future__ import annotations

from eval_harness.evals.domain.grade import GradeResult
from eval_harness.evals.domain.profile import LAB_CITATION_REGEX
from eval_harness.evals.graders.base import GradeContext, Grader, register_grader
from eval_harness.profiles.conventions import _rx, cited_ids, grounded_in

CITE = _rx(LAB_CITATION_REGEX)  # the lab agent's [doc-id] format (kept for importers of this module)


@register_grader("citation_grounding")
class CitationGrounding(Grader):
    """Every cited source in the answer must appear in a tool result (no invented sources).
    When ``expected.cited_sources`` is set, those ids must be cited too.
    The citation format comes from the agent profile (``conventions.citations``; default ``[doc-id]``).
    Skipped if the answer has no citations and none are expected, or the agent has no citation format."""

    description = "Cited [doc-ids] exist in tool results; expected sources are cited."

    def grade(self, ctx: GradeContext) -> GradeResult:
        conv = ctx.conventions
        found = cited_ids(conv, ctx.transcript.final_answer)
        if found is None:
            return self.skip("this agent profile defines no citation format (conventions.citations)")
        cited = set(found)
        expected = set(ctx.task.expected.cited_sources)
        if not cited and not expected:
            return self.skip("no citations in answer and none expected")
        seen = ctx.transcript.tool_result_text()
        invented = sorted(c for c in cited if not grounded_in(conv, c, seen))
        missing = sorted(expected - cited)
        ok = not invented and not missing
        why = []
        if invented:
            why.append(f"cited sources not in tool results: {invented}")
        if missing:
            why.append(f"expected sources not cited: {missing}")
        return self.passed(ok, "; ".join(why) or "citations grounded", invented=invented, missing=missing)

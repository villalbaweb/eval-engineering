from __future__ import annotations

import re

from eval_harness.evals.domain.grade import GradeResult
from eval_harness.evals.graders.base import GradeContext, Grader, register_grader

CITE = re.compile(r"\[([a-z0-9][a-z0-9\-_]*)\]")


@register_grader("citation_grounding")
class CitationGrounding(Grader):
    """Every [doc-id] cited in the answer must appear in a tool result (no invented sources).
    When ``expected.cited_sources`` is set, those ids must be cited too.
    Skipped if the answer has no citations and none are expected."""

    description = "Cited [doc-ids] exist in tool results; expected sources are cited."

    def grade(self, ctx: GradeContext) -> GradeResult:
        cited = set(CITE.findall(ctx.transcript.final_answer))
        expected = set(ctx.task.expected.cited_sources)
        if not cited and not expected:
            return self.skip("no citations in answer and none expected")
        seen = ctx.transcript.tool_result_text()
        invented = sorted(c for c in cited if f"[{c}]" not in seen)
        missing = sorted(expected - cited)
        ok = not invented and not missing
        why = []
        if invented:
            why.append(f"cited sources not in tool results: {invented}")
        if missing:
            why.append(f"expected sources not cited: {missing}")
        return self.passed(ok, "; ".join(why) or "citations grounded", invented=invented, missing=missing)

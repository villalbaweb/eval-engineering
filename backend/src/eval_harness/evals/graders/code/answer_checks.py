"""Deterministic checks on the final answer text."""

from __future__ import annotations

import re

from eval_harness.evals.domain.grade import GradeResult
from eval_harness.evals.graders.base import GradeContext, Grader, register_grader


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


@register_grader("answer_contains")
class AnswerContains(Grader):
    description = "Final answer contains every string in expected.answer_contains (case-insensitive)."

    def grade(self, ctx: GradeContext) -> GradeResult:
        need = ctx.task.expected.answer_contains
        if not need:
            return self.skip("task has no expected.answer_contains")
        ans = _norm(ctx.transcript.final_answer)
        missing = [s for s in need if _norm(s) not in ans]
        return self.passed(not missing, f"missing: {missing}" if missing else "all required strings present",
                           missing=missing)


@register_grader("answer_not_contains")
class AnswerNotContains(Grader):
    description = "Final answer contains none of expected.answer_not_contains."

    def grade(self, ctx: GradeContext) -> GradeResult:
        banned = ctx.task.expected.answer_not_contains
        if not banned:
            return self.skip("task has no expected.answer_not_contains")
        ans = _norm(ctx.transcript.final_answer)
        found = [s for s in banned if _norm(s) in ans]
        return self.passed(not found, f"forbidden strings present: {found}" if found else "no forbidden strings",
                           found=found)


@register_grader("answer_regex")
class AnswerRegex(Grader):
    description = "Final answer matches expected.answer_regex."

    def grade(self, ctx: GradeContext) -> GradeResult:
        rx = ctx.task.expected.answer_regex
        if not rx:
            return self.skip("task has no expected.answer_regex")
        ok = re.search(rx, ctx.transcript.final_answer, re.S | re.I) is not None
        return self.passed(ok, f"pattern {rx!r} {'matched' if ok else 'not found'}")


@register_grader("exact_match")
class ExactMatch(Grader):
    description = "Normalized final answer equals expected.reference_answer."

    def grade(self, ctx: GradeContext) -> GradeResult:
        ref = ctx.task.expected.reference_answer
        if ref is None:
            return self.skip("task has no expected.reference_answer")
        ok = _norm(ctx.transcript.final_answer) == _norm(ref)
        return self.passed(ok, "exact match" if ok else "answer differs from reference")

"""Shared plumbing for model-based (LLM-as-judge) graders."""

from __future__ import annotations

from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel

from eval_harness.core.settings import get_settings
from eval_harness.evals.domain.grade import GradeResult
from eval_harness.evals.graders.base import GradeContext, Grader
from eval_harness.llm.factory import make_chat_model
from eval_harness.llm.settings import judge_configured


class JudgeUnavailable(Exception):
    pass


def get_judge(model: str | None = None) -> BaseChatModel:
    """Judge model for the 'judge' role, or an explicit ``provider:model`` override (ensembles)."""
    if model:
        provider, _, name = model.partition(":")
        return make_chat_model("judge", provider=provider, model=name)
    if not judge_configured():
        raise JudgeUnavailable("no judge model configured (set JUDGE_MODEL in .env)")
    return make_chat_model("judge")


def load_rubric(name: str) -> str:
    """The active profile's rubric, else the shared one (``evals/rubrics``) of the same name."""
    s = get_settings()
    for d in dict.fromkeys((s.rubrics_dir, s.shared_rubrics_dir)):
        p = d / f"{name}.md"
        if p.exists():
            return p.read_text(encoding="utf-8")
    raise FileNotFoundError(f"rubric '{name}' not found in {s.rubrics_dir}")


class JudgeGrader(Grader):
    """Base for model graders: converts JudgeUnavailable into a skipped grade."""

    layer = 3

    def judge_call(self, ctx: GradeContext) -> GradeResult:  # pragma: no cover - interface
        raise NotImplementedError

    def grade(self, ctx: GradeContext) -> GradeResult:
        try:
            return self.judge_call(ctx)
        except JudgeUnavailable as e:
            return self.skip(str(e))


def verdict(res: dict[str, Any]) -> tuple[bool, float, str]:
    """openevals result -> (passed, score, comment)."""
    score = res.get("score")
    if isinstance(score, bool):
        return score, 1.0 if score else 0.0, str(res.get("comment", ""))
    val = float(score or 0.0)
    return val >= 0.5, val, str(res.get("comment", ""))

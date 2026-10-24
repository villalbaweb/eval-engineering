"""Model-based graders, exercised with the offline scripted judge (plumbing, not judgement quality)."""

import pytest

from eval_harness.evals.domain.outcome import Outcome
from eval_harness.evals.domain.task import Task
from eval_harness.evals.domain.transcript import ToolCallRecord, Transcript
from eval_harness.evals.graders.base import GradeContext, grader_registry


def ctx(answer="a fine answer", with_tools=True, **expected):
    msgs = [{"role": "user", "content": "q"}]
    calls = []
    if with_tools:
        calls = [ToolCallRecord(id="c1", name="knowledge_base_search", result="[doc] text")]
        msgs += [{"role": "assistant", "content": "", "tool_calls": [
            {"id": "c1", "type": "function", "function": {"name": "knowledge_base_search", "arguments": "{}"}}]},
            {"role": "tool", "tool_call_id": "c1", "content": "[doc] text"}]
    msgs.append({"role": "assistant", "content": answer})
    task = Task(id="t", input={"messages": [{"role": "user", "content": "q"}]}, expected=expected)
    return GradeContext(task, Transcript(messages=msgs, tool_calls=calls), Outcome())


def grade(type_, c, **args):
    return grader_registry.get(type_)(name=type_, **args).grade(c)


def test_llm_judge_runs_with_rubric_and_returns_verdict():
    r = grade("llm_judge", ctx(final_answer_criteria=["x"]), rubric="correctness")
    assert r.passed is True and r.layer == 3 and r.details["rubric"] == "correctness"


def test_llm_judge_skips_when_required_field_missing():
    r = grade("llm_judge", ctx(), rubric="correctness", requires=["final_answer_criteria"])
    assert r.skipped and "final_answer_criteria" in r.rationale


def test_llm_judge_fails_when_judge_says_so():
    r = grade("llm_judge", ctx(answer="bad [[fail]]"), rubric="conciseness")
    assert r.passed is False


def test_groundedness_skips_without_tool_results():
    assert grade("groundedness", ctx(with_tools=False)).skipped
    assert grade("groundedness", ctx()).passed


def test_trajectory_judge_with_and_without_reference():
    assert grade("trajectory_judge", ctx()).details["with_reference"] is False
    r = grade("trajectory_judge", ctx(tool_calls=[{"name": "knowledge_base_search"}]))
    assert r.details["with_reference"] is True
    assert grade("trajectory_judge", ctx(with_tools=False)).skipped


def test_pairwise_swap_controls_for_position_bias():
    c = ctx(reference_answer="a reference")
    swapped = grade("pairwise_judge", c, swap=True)
    # the scripted judge always answers "A is better": that is pure position bias, and swapping exposes it
    assert swapped.details["outcome"] == "inconsistent" and swapped.details["position_bias"] and swapped.passed
    single = grade("pairwise_judge", c, swap=False)
    assert single.details == {"swapped": False} and single.passed  # without swapping the bias looks like a win
    assert grade("pairwise_judge", ctx()).skipped


def test_judge_ensemble_reports_votes():
    r = grade("judge_ensemble", ctx(), rubric="correctness")
    assert r.passed and r.details["unanimous"] and len(r.details["votes"]) == 3
    r2 = grade("judge_ensemble", ctx(answer="x [[fail]]"), rubric="correctness", models=["fake:scripted", "fake:scripted"])
    assert not r2.passed and r2.score == 0.0


def test_missing_judge_model_skips_instead_of_silently_using_agent_model(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
    monkeypatch.delenv("JUDGE_MODEL", raising=False)
    monkeypatch.delenv("JUDGE_PROVIDER", raising=False)
    r = grade("llm_judge", ctx())
    assert r.skipped and "JUDGE_MODEL" in r.rationale


def test_human_review_uses_annotations():
    from eval_harness.storage.repositories import annotations

    c = ctx()
    c.trial_id, c.experiment_id = "t_human", "exp_human"
    assert grade("human_review", c).skipped
    annotations.upsert("t_human", "exp_human", good=False, failure_tags=["ungrounded"], note="invented")
    r = grade("human_review", c)
    assert r.passed is False and r.label == "ungrounded"


@pytest.mark.parametrize("rubric", ["correctness", "groundedness", "conciseness", "scope_and_safety", "pairwise"])
def test_all_shipped_rubrics_format_cleanly(rubric):
    from eval_harness.evals.graders.model.judge_base import load_rubric

    text = load_rubric(rubric)
    fields = {"inputs": "i", "outputs": "o", "reference_outputs": "r", "criteria": "c", "tool_results": "t",
              "response_a": "a", "response_b": "b"}
    assert text.format(**fields)  # no stray braces / unknown placeholders

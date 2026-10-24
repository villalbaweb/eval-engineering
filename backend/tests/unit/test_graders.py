import asyncio

from eval_harness.evals.domain.outcome import Outcome
from eval_harness.evals.domain.suite import GraderSpec
from eval_harness.evals.domain.task import Task
from eval_harness.evals.domain.transcript import ToolCallRecord, Transcript
from eval_harness.evals.graders.base import GradeContext, GraderPipeline, grader_registry


def task(**expected) -> Task:
    return Task(id="t1", tags=["x"], input={"messages": [{"role": "user", "content": "q"}]}, expected=expected)


def call(name, args=None, result="ok", error=False, fault=None):
    return ToolCallRecord(id=f"c-{name}", name=name, args=args or {}, result=result, error=error, injected_fault=fault)


def transcript(answer="done", calls=(), skills=()):
    msgs = [{"role": "user", "content": "q"}]
    for c in calls:
        msgs.append({"role": "assistant", "content": "", "tool_calls": [
            {"id": c.id, "type": "function", "function": {"name": c.name, "arguments": "{}"}}]})
        msgs.append({"role": "tool", "tool_call_id": c.id, "content": c.result})
    msgs.append({"role": "assistant", "content": answer})
    return Transcript(messages=msgs, tool_calls=list(calls), skills_loaded=list(skills))


def grade(type_, t: Task, tr: Transcript, **args):
    g = grader_registry.get(type_)(name=type_, **args)
    return g.grade(GradeContext(t, tr, Outcome(final_answer=tr.final_answer)))


def test_answer_contains_and_skip():
    assert grade("answer_contains", task(answer_contains=["Foo"]), transcript("a foo b")).passed
    r = grade("answer_contains", task(answer_contains=["zzz"]), transcript("a foo b"))
    assert r.passed is False and "zzz" in r.rationale
    assert grade("answer_contains", task(), transcript()).skipped


def test_tool_called_with_args_subset():
    t = task(tool_calls=[{"name": "stats", "args": {"n": 10}}])
    assert grade("tool_called", t, transcript(calls=[call("stats", {"n": 10, "k": 3})])).passed
    assert not grade("tool_called", t, transcript(calls=[call("stats", {"n": 99})])).passed
    assert not grade("tool_called", t, transcript()).passed


def test_trajectory_match_modes():
    t = task(tool_calls=[{"name": "a"}, {"name": "b"}], trajectory_mode="superset")
    assert grade("trajectory_match", t, transcript(calls=[call("a"), call("b"), call("c")])).passed
    assert not grade("trajectory_match", t, transcript(calls=[call("a")])).passed
    # subset: the agent may not call anything outside the reference
    t2 = task(tool_calls=[{"name": "a"}, {"name": "b"}], trajectory_mode="subset")
    assert grade("trajectory_match", t2, transcript(calls=[call("a")])).passed
    assert not grade("trajectory_match", t2, transcript(calls=[call("a"), call("zzz")])).passed
    # unordered
    t3 = task(tool_calls=[{"name": "a"}, {"name": "b"}], trajectory_mode="unordered")
    assert grade("trajectory_match", t3, transcript(calls=[call("b"), call("a")])).passed


def test_trajectory_subsequence_partial_credit():
    t = task(tool_calls=[{"name": "a"}, {"name": "b"}, {"name": "c"}])
    r = grade("trajectory_subsequence", t, transcript(calls=[call("a"), call("x"), call("b")]))
    assert abs(r.score - 2 / 3) < 1e-9 and r.passed is False


def test_skill_selection_scores_and_forbidden():
    t = task(skills_loaded=["a"], forbidden_skills=["z"])
    assert grade("skill_selection", t, transcript(skills=["a"])).passed
    r = grade("skill_selection", t, transcript(skills=["a", "z"]))
    assert not r.passed and "forbidden" in r.rationale
    assert not grade("skill_selection", t, transcript(skills=[])).passed
    # extra skills are tolerated unless strict_precision
    assert grade("skill_selection", task(skills_loaded=["a"]), transcript(skills=["a", "b"])).passed
    assert not grade("skill_selection", task(skills_loaded=["a"]), transcript(skills=["a", "b"]),
                     strict_precision=True).passed


def test_step_efficiency_detects_loops():
    same = [call("a", {"q": 1}), call("a", {"q": 1})]
    assert not grade("step_efficiency", task(), transcript(calls=same)).passed
    assert grade("step_efficiency", task(), transcript(calls=[call("a", {"q": 1}), call("a", {"q": 2})])).passed


def test_error_recovery_cases():
    fail = call("kb", error=True, result="ERROR: 503", fault="error:kb")
    skip = grade("error_recovery", task(), transcript(calls=[call("kb")]))
    assert skip.skipped
    recovered = grade("error_recovery", task(), transcript("ok", calls=[fail, call("kb")]))
    assert recovered.passed and recovered.details["recovered"]
    honest = grade("error_recovery", task(), transcript("The knowledge base was unavailable.", calls=[fail]))
    assert honest.passed
    silent = grade("error_recovery", task(), transcript("pass@k is the probability of success.", calls=[fail]))
    assert not silent.passed


def test_citation_grounding_catches_invented_sources():
    calls = [call("knowledge_base_search", result="[pass-at-k] text")]
    assert grade("citation_grounding", task(), transcript("see [pass-at-k]", calls=calls)).passed
    r = grade("citation_grounding", task(), transcript("see [made-up-doc]", calls=calls))
    assert not r.passed and "made-up-doc" in r.rationale
    assert not grade("citation_grounding", task(cited_sources=["pass-at-k"]), transcript("no cites", calls=calls)).passed
    assert grade("citation_grounding", task(), transcript("no cites")).skipped


def test_refusal_and_guardrail():
    assert grade("refusal", task(should_refuse=True), transcript("I can only help with evaluation engineering.")).passed
    assert not grade("refusal", task(should_refuse=False), transcript("I cannot help with that.")).passed
    tr = transcript()
    tr.meta["guardrail_events"] = [{"kind": "prompt_injection_suspected"}]
    assert grade("guardrail_tripwire", task(), tr, expect="prompt_injection_suspected").passed
    assert not grade("guardrail_tripwire", task(), tr).passed


def test_budget():
    tr = transcript(calls=[call("a")] * 3)
    assert not grade("budget", task(), tr, max_tool_calls=2).passed
    assert grade("budget", task(), tr, max_tool_calls=5).passed


def test_json_schema():
    assert grade("json_schema", task(), transcript('```json\n{"a": 1}\n```'), required_keys=["a"]).passed
    assert not grade("json_schema", task(), transcript("not json"), required_keys=["a"]).passed


def test_pipeline_fail_fast_skips_expensive_layers_and_when_tags():
    specs = [GraderSpec(type="answer_contains"), GraderSpec(type="groundedness"),
             GraderSpec(type="refusal", when_tags=["never"])]
    t = task(answer_contains=["needle"])
    ctx = GradeContext(t, transcript("haystack", calls=[call("kb")]), Outcome())
    res = asyncio.run(GraderPipeline(specs, fail_fast=True).run(ctx))
    by = {r.grader: r for r in res}
    assert by["answer_contains"].passed is False
    assert by["groundedness"].skipped and "cheaper" in by["groundedness"].rationale
    assert "refusal" not in by  # filtered out by when_tags
    res2 = asyncio.run(GraderPipeline(specs, fail_fast=False).run(ctx))
    assert not {r.grader: r for r in res2}["groundedness"].rationale.startswith("skipped: a cheaper")


def test_broken_grader_does_not_crash_pipeline(monkeypatch):
    g_cls = grader_registry.get("answer_contains")
    monkeypatch.setattr(g_cls, "grade", lambda self, ctx: 1 / 0)
    res = asyncio.run(GraderPipeline([GraderSpec(type="answer_contains")]).run(
        GradeContext(task(answer_contains=["x"]), transcript(), Outcome())))
    assert res[0].skipped and "grader error" in res[0].rationale

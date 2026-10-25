"""P2: profile conventions replace hard-coded trace rules; the defaults reproduce the old behaviour exactly."""

import json

import pytest

from eval_harness.evals.data_sources.traces.base import TraceRecord, normalize_messages, transcript_from_messages
from eval_harness.evals.data_sources.traces.importer import apply_conventions
from eval_harness.evals.domain.outcome import Outcome
from eval_harness.evals.domain.profile import CitationRule, Conventions, Profile, SkillRule, ToolErrorRule
from eval_harness.evals.domain.task import Task
from eval_harness.evals.domain.transcript import ToolCallRecord, Transcript
from eval_harness.evals.graders.base import GradeContext
from eval_harness.evals.graders.code.citation_grounding import CitationGrounding


def old_rules(messages):
    """Frozen copy of the pre-profiles hard-coded logic (the reference the defaults must reproduce)."""
    results = {m.get("tool_call_id"): m for m in messages if m.get("role") == "tool"}
    errors, skills = [], []
    for m in messages:
        for tc in m.get("tool_calls") or []:
            fn = tc.get("function", {})
            args = json.loads(fn.get("arguments") or "{}")
            text = results.get(tc.get("id"), {}).get("content", "")
            errors.append(text.startswith("ERROR"))
            name = fn.get("name", "")
            if name == "load_skill" and args.get("name"):
                skills.append(args["name"])
            elif name.startswith("load_skill_"):
                skills.append(name[len("load_skill_"):].replace("_", "-"))
    return errors, list(dict.fromkeys(skills))


def call(cid, name, args=None):
    return {"id": cid, "type": "function", "function": {"name": name, "arguments": json.dumps(args or {})}}


def convo(*pairs):
    """pairs of (tool_call, result_text) -> OpenAI messages."""
    msgs = [{"role": "user", "content": "q"}]
    msgs.append({"role": "assistant", "content": "", "tool_calls": [c for c, _ in pairs]})
    msgs += [{"role": "tool", "tool_call_id": c["id"], "content": r} for c, r in pairs]
    msgs.append({"role": "assistant", "content": "done"})
    return msgs


CASES = [
    convo((call("1", "load_skill_error_analysis"), "skill text"), (call("2", "load_skill_rubric_authoring"), "ok")),
    convo((call("1", "load_skill", {"name": "pass-at-k"}), "x"), (call("2", "load_skill", {}), "x")),
    convo((call("1", "knowledge_base_search", {"query": "a"}), "ERROR: 503"), (call("2", "web_search"), "fine")),
    convo((call("1", "load_skill_a_b"), "ERROR: missing"), (call("2", "load_skill_a_b"), "again")),
    convo((call("1", "stats_calculator"), "No relevant passages found.")),
]


@pytest.mark.parametrize("msgs", CASES)
def test_default_conventions_reproduce_the_old_rules(msgs):
    t = transcript_from_messages(msgs)
    errors, skills = old_rules(msgs)
    assert [c.error for c in t.tool_calls] == errors
    assert t.skills_loaded == skills


def test_alternative_conventions_for_another_agent():
    conv = Conventions(
        skills=[SkillRule(tool="use_capability", arg="name")],
        tool_error=[ToolErrorRule(result_json_key="error"), ToolErrorRule(result_regex=r"^HTTP 5\d\d")],
        citations=None)
    msgs = convo((call("1", "use_capability", {"name": "refunds"}), '{"ok": true}'),
                 (call("2", "search_orders"), '{"error": "timeout"}'),
                 (call("3", "lookup"), "HTTP 503 Service Unavailable"),
                 (call("4", "load_skill_x"), "ERROR text is not an error for this agent"))
    t = transcript_from_messages(msgs, conventions=conv)
    assert t.skills_loaded == ["refunds"]  # load_skill_* means nothing for this agent
    assert [c.error for c in t.tool_calls] == [False, True, True, False]


def test_message_status_rule_reads_statuses_kept_out_of_the_messages():
    raw = [{"role": "user", "content": "q"},
           {"role": "assistant", "content": "", "tool_calls": [{"id": "1", "name": "x", "args": {}}]},
           {"role": "tool", "tool_call_id": "1", "content": "boom", "status": "error"}]
    statuses: dict[str, str] = {}
    msgs = normalize_messages(raw, statuses)
    assert statuses == {"1": "error"} and "status" not in msgs[2]  # message shape unchanged
    only_status = Conventions(tool_error=[ToolErrorRule(message_status="error")])
    assert transcript_from_messages(msgs, conventions=only_status, statuses=statuses).tool_calls[0].error
    assert not transcript_from_messages(msgs, conventions=only_status).tool_calls[0].error
    # lab defaults ignore the status (pre-profiles behaviour): only the ERROR prefix counts
    assert not transcript_from_messages(msgs, statuses=statuses).tool_calls[0].error


def test_langsmith_import_keeps_pre_profiles_error_semantics():
    """The LangSmith path is not reachable by the offline golden run, so pin it here."""
    from types import SimpleNamespace
    from uuid import uuid4

    from eval_harness.evals.data_sources.traces.langsmith import run_to_record

    msgs = [{"type": "human", "content": "q"},
            {"type": "ai", "content": "", "tool_calls": [{"id": "1", "name": "load_skill_x", "args": {}},
                                                          {"id": "2", "name": "kb", "args": {}}]},
            {"type": "tool", "tool_call_id": "1", "content": "Error invoking tool", "status": "error"},
            {"type": "tool", "tool_call_id": "2", "content": "ERROR: 503", "status": "error"},
            {"type": "ai", "content": "answer"}]
    run = SimpleNamespace(id=uuid4(), inputs={"messages": msgs[:1]}, outputs={"messages": msgs}, extra={},
                          error=None, start_time=None, end_time=None)
    t = run_to_record(run).transcript
    assert [c.error for c in t.tool_calls] == [False, True] and t.skills_loaded == ["x"]
    strict = Conventions(tool_error=[ToolErrorRule(message_status="error")])
    assert [c.error for c in run_to_record(run, conventions=strict).transcript.tool_calls] == [True, True]


def test_import_derives_calls_only_for_message_only_records():
    conv = Conventions(skills=[SkillRule(tool="use_capability", arg="name")])
    msgs = convo((call("1", "use_capability", {"name": "refunds"}), "ok"))
    bare = TraceRecord(id="a", input_messages=msgs[:1], transcript=Transcript(messages=msgs))
    assert apply_conventions(bare, conv).transcript.skills_loaded == ["refunds"]
    built = TraceRecord(id="b", input_messages=msgs[:1], transcript=Transcript(
        messages=msgs, tool_calls=[ToolCallRecord(name="use_capability")], skills_loaded=["kept"]))
    assert apply_conventions(built, conv).transcript.skills_loaded == ["kept"]  # untouched


def _cite_ctx(answer, results, profile=None, expected=()):
    task = Task(id="t", input={"messages": [{"role": "user", "content": "q"}]},
                expected={"cited_sources": list(expected)})
    t = Transcript(messages=[{"role": "assistant", "content": answer}],
                   tool_calls=[ToolCallRecord(name="kb", result=results)])
    return GradeContext(task, t, Outcome(final_answer=answer), profile=profile)


def test_citation_grounding_uses_the_profile_format():
    g = CitationGrounding()
    assert g.grade(_cite_ctx("see [pass-at-k]", "[pass-at-k] text")).passed  # lab default
    assert g.grade(_cite_ctx("see [a]", "[a]")).passed  # one-char ids still match the old regex
    assert not g.grade(_cite_ctx("see [made-up]", "[pass-at-k]")).passed
    other = Profile(name="x", conventions=Conventions(citations=CitationRule(regex=r"\(source: (\w+)\)",
                                                                             in_results="id={id}")))
    assert g.grade(_cite_ctx("per (source: KB42)", "doc id=KB42", other)).passed
    none = Profile(name="y", conventions=Conventions(citations=None))
    r = g.grade(_cite_ctx("see [pass-at-k]", "", none))
    assert r.skipped and "no citation format" in r.rationale  # skipped with a reason, never a fake pass

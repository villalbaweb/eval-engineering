from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from eval_harness.evals.data_sources import quality, review
from eval_harness.evals.data_sources.synthesis.base import SynthesisConfig, generator_registry
from eval_harness.evals.data_sources.traces.base import normalize_messages, transcript_from_messages
from eval_harness.evals.data_sources.traces.langsmith import run_to_record
from eval_harness.evals.domain.task import Task


def mk(i, text, **exp):
    return Task(id=f"c{i}", input={"messages": [{"role": "user", "content": text}]}, expected=exp)


def test_pii_scrub():
    s = quality.scrub_pii("mail me at jane.doe@example.com, key sk-abcdefghijklmnop1234, card 4111 1111 1111 1111")
    assert "example.com" not in s and "sk-abc" not in s and "4111" not in s


def test_dedupe_near_duplicates_against_existing():
    new = [mk(1, "How do I write a rubric for an LLM judge"), mk(2, "How do I write a rubric for an LLM judge?"),
           mk(3, "Compare two experiments")]
    kept, dropped = quality.dedupe(new)
    assert [t.id for t in kept] == ["c1", "c3"] and dropped == ["c2"]
    kept2, _ = quality.dedupe([mk(9, "compare two experiments please")], existing=[mk(3, "Compare two experiments")], threshold=0.6)
    assert kept2 == []


def test_leak_check_flags_inputs_that_contain_the_answer():
    t = mk(1, "The answer is: coverage is the share of bad outputs failed by the grader", answer_contains=["share of bad outputs failed"])
    assert quality.leaks(t)
    assert not quality.leaks(mk(2, "what is coverage?", answer_contains=["share of bad outputs failed"]))


def test_review_queue_roundtrip(tmp_evals):
    res = review.save_candidates([mk(1, "unique question about trajectory graders alpha beta gamma delta")], existing=[])
    assert res["queued"] == 1
    assert review.get_candidate("c1")
    out = review.accept(["c1"], group="unit_group")
    assert out["accepted"] == 1 and review.get_candidate("c1") is None
    from eval_harness.evals.datasets.loader import load_tasks

    assert any(t.id == "c1" for t in load_tasks(["unit_group"]))


def test_generators_produce_valid_labelled_tasks_offline():
    for gen, kw in [("dimensional", {"dimensions": {"intent": {"design a rubric": {"skills_loaded": ["rubric-authoring"]}},
                                                     "persona": ["novice engineer", "terse manager"]}}),
                    ("adversarial", {}), ("skill_targeted", {}), ("trace_seeded", {"options": {"seed_datasets": ["tool-use"]}}),
                    ("multiturn_personas", {"dimensions": {"topic": ["trajectories"], "persona": ["impatient engineer"]}})]:
        cfg = SynthesisConfig(name=gen, generator=gen, count=4, **kw)
        tasks = generator_registry.get(gen)(cfg).generate()
        assert tasks and all(t.user_text for t in tasks), gen
        assert all(t.source == f"synthetic:{gen}" for t in tasks)


def test_dimensional_label_comes_from_tuple_not_text():
    cfg = SynthesisConfig(name="d", generator="dimensional", count=3, dimensions={
        "intent": {"design a rubric": {"skills_loaded": ["rubric-authoring"]}}, "persona": ["a", "b", "c"]})
    for t in generator_registry.get("dimensional")(cfg).generate():
        assert t.expected.skills_loaded == ["rubric-authoring"]
        assert set(t.metadata["dims"]) == {"intent", "persona"}


def test_normalize_langchain_messages_and_rebuild_transcript():
    raw = [{"type": "human", "content": "hi"},
           {"type": "ai", "content": "", "tool_calls": [{"id": "1", "name": "load_skill_rubric_authoring", "args": {}}]},
           {"type": "tool", "content": "body", "tool_call_id": "1"},
           {"type": "ai", "content": "done"}]
    msgs = normalize_messages(raw)
    assert [m["role"] for m in msgs] == ["user", "assistant", "tool", "assistant"]
    t = transcript_from_messages(msgs)
    assert t.skills_loaded == ["rubric-authoring"] and t.tool_names == ["load_skill_rubric_authoring"]
    assert t.final_answer == "done"


def test_langsmith_run_to_record():
    run = SimpleNamespace(id=uuid4(), inputs={"messages": [{"type": "human", "content": "q"}]},
                          outputs={"messages": [{"type": "human", "content": "q"}, {"type": "ai", "content": "a"}]},
                          extra={"metadata": {"source": "traffic"}}, error=None,
                          start_time=datetime(2026, 1, 1, tzinfo=UTC), end_time=datetime(2026, 1, 1, 0, 0, 2, tzinfo=UTC))
    rec = run_to_record(run, {"thumbs": 0})
    assert rec.source == "traffic" and rec.transcript.latency_s == 2.0 and rec.feedback == {"thumbs": 0}
    assert run_to_record(SimpleNamespace(id=uuid4(), inputs={}, outputs={}, extra={}, error=None)) is None

import asyncio

import pytest

from eval_harness.evals.analysis.calibration import calibrate
from eval_harness.evals.analysis.compare import compare
from eval_harness.evals.runner.service import prepare_regrade, prepare_runner
from eval_harness.storage.repositories import annotations, experiments, task_snapshots, trials


def run_suite(suite, **ov):
    events = []
    runner = prepare_runner(suite, overrides=ov, on_event=events.append, hooks=[])
    exp = asyncio.run(runner.run())
    return exp, events


@pytest.fixture(scope="module")
def smoke():
    return run_suite("smoke")


def test_smoke_suite_runs_stores_and_summarizes(smoke):
    exp, events = smoke
    assert exp.status == "completed" and exp.done_trials == exp.total_trials == 8
    s = exp.summary
    assert s["pass_rates"]["trial_pass_rate"] == 1.0 and s["pass_rates"]["n_tasks"] == 8
    assert {"by_tag", "by_grader", "flakiness", "cost_latency"} <= set(s)
    assert [e["type"] for e in events][0] == "experiment_started" and events[-1]["type"] == "experiment_done"
    assert len(trials.for_experiment(exp.id)) == 8 and len(task_snapshots.for_experiment(exp.id)) == 8
    assert experiments.get(exp.id).summary["pass_rates"]["k"] == 1


def test_snapshot_explains_the_run(smoke):
    snap = smoke[0].snapshot
    assert snap["models"]["agent"]["provider"] == "fake"
    assert snap["target"]["agent_config"]["name"] == "copilot-baseline"
    assert snap["target"]["skills"] and snap["tasks_hash"] and snap["target"]["prompt_sha"]


def test_k_trials_produce_pass_at_k_and_flakiness_buckets():
    exp, _ = run_suite("skill-selection", k=3, max_tasks=3)
    pr = exp.summary["pass_rates"]
    assert pr["k"] == 3 and pr["n_trials"] == 9 and pr["mean_pass_at_k"] >= pr["mean_pass_pow_k"]
    assert exp.summary["flakiness"]["informative"] is True


def test_overrides_switch_agent_and_loader_mode():
    exp, _ = run_suite("skill-selection", agent="copilot-generic-loader", k=1)
    assert exp.snapshot["target"]["skill_loader_mode"] == "generic"
    assert exp.summary["pass_rates"]["trial_pass_rate"] == 1.0  # skill_selection is loader-mode agnostic


def test_ablation_without_skills_fails_skill_selection():
    exp, _ = run_suite("skill-selection", agent="copilot-no-skills", k=1)
    assert exp.summary["pass_rates"]["trial_pass_rate"] < 0.5


def test_model_graders_are_skipped_without_judge_but_run_with_offline_judge():
    # offline provider counts as a configured judge, so llm graders run (scripted verdicts)
    exp, _ = run_suite("capability", k=1, max_tasks=3)
    g = exp.summary["by_grader"]
    assert "correctness" in g


def test_regrade_reuses_transcripts_without_running_the_agent(smoke):
    src = smoke[0]
    exp = asyncio.run(prepare_regrade(src.id, graders=[{"type": "answer_contains"}], name="rg").run())
    assert exp.snapshot["regrade_of"] == src.id and exp.target == "replay"
    old = {t.task_id: t.transcript.final_answer for t in trials.for_experiment(src.id)}
    new = {t.task_id: t.transcript.final_answer for t in trials.for_experiment(exp.id)}
    assert old == new


def test_fault_suite_flags_unrecovered_failures():
    exp, _ = run_suite("robustness", k=1)
    assert "error_recovery" in exp.summary["by_grader"]


def test_multiturn_target_continues_the_conversation():
    exp, _ = run_suite("multi-turn", k=1)
    ts = trials.for_experiment(exp.id)
    t = next(x for x in ts if x.task_id == "mt-rubric-then-kb-01")
    assert t.transcript.meta.get("multi_turn") and sum(1 for m in t.transcript.messages if m["role"] == "user") >= 2
    assert "knowledge_base_search" in t.transcript.tool_names  # triggered by the scripted follow-up


def test_compare_two_experiments_reports_regressions():
    a, _ = run_suite("skill-selection", agent="copilot-baseline", k=1)
    b, _ = run_suite("skill-selection", agent="copilot-no-skills", k=1)
    r = compare(a.id, b.id)
    assert r["delta"] < 0 and r["regressions"] and r["two_proportion_z"]["p_value"] < 0.05
    assert r["per_task"][0]["delta"] <= r["per_task"][-1]["delta"]  # regressions first


def test_calibration_from_human_labels():
    exp, _ = run_suite("skill-selection", k=1)
    ts = trials.for_experiment(exp.id)
    for i, t in enumerate(ts):
        annotations.upsert(t.id, exp.id, good=(i % 2 == 0), failure_tags=[] if i % 2 == 0 else ["wrong_skill"], note="")
    r = calibrate(exp.id)
    assert r["n_labeled"] == len(ts) and "skill_selection" in r["graders"]
    m = r["graders"]["skill_selection"]
    assert m["n"] == len(ts) and 0 <= m["ffr"] <= 1
    assert r["failure_tags"]["wrong_skill"] > 0


def test_trace_target_grades_logged_transcripts_without_running_the_agent():
    from eval_harness.evals.data_sources.traces.base import transcript_from_messages
    from eval_harness.evals.domain.task import Task

    msgs = [{"role": "user", "content": "q"}, {"role": "assistant", "content": "a"}]
    tasks = [Task(id="trace-x", input={"messages": msgs[:1]}, source="traces:jsonl",
                  metadata={"transcript": transcript_from_messages(msgs).model_dump(mode="json")})]
    runner = prepare_runner("traces", tasks=tasks, hooks=[])
    exp = asyncio.run(runner.run())
    assert exp.status == "completed" and exp.target == "trace"
    assert trials.for_experiment(exp.id)[0].transcript.final_answer == "a"

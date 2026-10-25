"""P3: variants, modes and capabilities in the runner; a second (trace-only) agent next to the copilot."""

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from eval_harness.evals.analysis.compare import compare  # noqa: E402
from eval_harness.evals.runner.service import CapabilityError, prepare_runner  # noqa: E402
from eval_harness.integrations.langsmith.datasets import dataset_name  # noqa: E402
from eval_harness.profiles import use_profile  # noqa: E402
from eval_harness.storage.repositories import trials  # noqa: E402
from profile_fixtures import make_demo_profile, private_evals  # noqa: E402


@pytest.fixture()
def evals(tmp_path, tmp_evals):
    with private_evals(tmp_evals, tmp_path / "evals") as d:
        make_demo_profile(d)
        yield d


def run(suite, **ov):
    r = prepare_runner(suite, hooks=[], overrides=ov)
    return r, asyncio.run(r.run())


def test_copilot_runs_unchanged_next_to_another_profile(evals):
    r, exp = run("smoke", max_tasks=2)
    assert exp.status == "completed" and r.suite.target == "local_agent" and r.suite.agent == "copilot-baseline"
    snap = exp.snapshot
    assert (snap["profile"], snap["variant"], snap["mode"]) == ("copilot", "copilot-baseline", "live")
    assert "variant" not in snap["suite"] and "mode" not in snap["suite"]  # old snapshot shape kept
    assert "rerun" in snap["capabilities"]
    assert dataset_name("smoke") == "eval-eng/smoke"  # existing LangSmith names unchanged


def test_variant_and_legacy_agent_select_the_same_config(evals):
    a, _ = run("smoke", max_tasks=1, variant="copilot-no-skills")
    b, _ = run("smoke", max_tasks=1, agent="copilot-no-skills")
    assert a.target.cfg == b.target.cfg and a.target.cfg.skills == "none"
    c, _ = run("smoke", max_tasks=1, target="local_agent", mode="trace")  # explicit legacy target wins
    assert c.suite.target == "local_agent"
    with pytest.raises(FileNotFoundError, match="agent config 'nope' not found"):  # same error as before
        run("smoke", max_tasks=1, agent="nope")
    from eval_harness.evals.datasets.loader import load_suite
    from eval_harness.evals.runner.service import resolve_run

    # grading stored transcripts never needed the agent: an unknown name is still not an error there
    suite, target, facts = resolve_run(load_suite("traces"), {"agent": "nope"})
    assert target == "trace" and facts["variant"] is None


def test_trace_only_profile_grades_with_its_own_conventions(evals):
    with use_profile("demo"):
        r, exp = run("traces")
        assert exp.status == "completed" and r.suite.target == "trace" and exp.snapshot["profile"] == "demo"
        rows = {t.task_id: t for t in trials.for_experiment(exp.id)}
        g = {k: {x.grader: x for x in v.grades} for k, v in rows.items()}
        assert g["logged-0"]["skill_selection"].passed and g["logged-1"]["skill_selection"].passed  # use_capability
        assert g["logged-0"]["tool_errors"].passed and not g["logged-1"]["tool_errors"].passed  # {"error": ...}
        assert g["logged-0"]["citation_grounding"].skipped  # this agent has no citation format
        assert dataset_name("traces") == "demo-agent/traces"


def test_capabilities_are_checked_before_anything_runs(evals):
    with use_profile("demo"):
        with pytest.raises(CapabilityError, match="cannot be run from the lab"):
            prepare_runner("traces", hooks=[], overrides={"mode": "live"})
        with pytest.raises(CapabilityError, match="multi-turn"):
            prepare_runner("traces", hooks=[], overrides={"mode": "multiturn"})
    with pytest.raises(CapabilityError, match="cannot be run"):
        prepare_runner("smoke", hooks=[], overrides={"variant": "demo:prod-traces", "mode": "live"})


def test_compare_flags_runs_of_different_agents(evals):
    _, a = run("smoke", max_tasks=1)
    with use_profile("demo"):
        _, b = run("traces")
    r = compare(a.id, b.id)
    assert any(w.startswith("different agents") for w in r["warnings"])
    assert {"path": "profile", "a": "copilot", "b": "demo"} in r["config_changes"]

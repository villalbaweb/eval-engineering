"""High-level entry points shared by the CLI and the API."""

from __future__ import annotations

from typing import Any

from eval_harness.evals.datasets.loader import load_suite, suite_tasks
from eval_harness.evals.domain.suite import GraderSpec, Suite
from eval_harness.evals.domain.task import Task
from eval_harness.evals.runner.executor import EventCb, ExperimentRunner
from eval_harness.evals.runner.hooks import RunnerHook
from eval_harness.evals.targets.base import target_registry
from eval_harness.storage.repositories import task_snapshots


def default_hooks() -> list[RunnerHook]:
    from eval_harness.integrations.langsmith.mirror import ExperimentMirror

    return [ExperimentMirror()]


def prepare_runner(suite_name: str, *, overrides: dict[str, Any] | None = None, name: str | None = None,
                   on_event: EventCb | None = None, hooks: list[RunnerHook] | None = None,
                   tasks: list[Task] | None = None) -> ExperimentRunner:
    """Build a runner. ``overrides`` may set: k, concurrency, tool_mode, agent, target, max_tasks,
    target_options (dict), graders (list[GraderSpec dict]), datasets (list of groups/paths) - the same
    knobs the UI exposes. ``datasets`` uses the suite as a template (graders, target, agent) for other
    data, and drops the suite's tag/kind filters, which were written for its own datasets."""
    ov = dict(overrides or {})
    suite: Suite = load_suite(suite_name)
    if ov.get("datasets"):
        suite = suite.model_copy(update={"datasets": list(ov["datasets"]), "include_tags": [],
                                         "exclude_tags": [], "kinds": []})
    run_over = {k: ov[k] for k in ("k", "concurrency", "tool_mode", "timeout_s", "max_tasks", "fail_fast")
                if ov.get(k) is not None}
    suite = suite.model_copy(update={
        "run": suite.run.model_copy(update=run_over),
        **({"agent": ov["agent"]} if ov.get("agent") else {}),
        **({"target": ov["target"]} if ov.get("target") else {}),
        **({"graders": [GraderSpec.model_validate(g) for g in ov["graders"]]} if ov.get("graders") else {}),
    })
    the_tasks = tasks if tasks is not None else suite_tasks(suite)
    if run_over.get("max_tasks"):
        the_tasks = the_tasks[: run_over["max_tasks"]]
    if not the_tasks:
        raise ValueError(f"suite '{suite_name}' selects no tasks"
                         + (f" from datasets {suite.datasets}" if ov.get("datasets") else ""))
    target = target_registry.get(suite.target).create(suite, **(ov.get("target_options") or {}))
    return ExperimentRunner(suite, the_tasks, target, name=name, on_event=on_event,
                            hooks=hooks if hooks is not None else default_hooks())


def prepare_regrade(experiment_id: str, *, suite_name: str | None = None, graders: list[dict] | None = None,
                    name: str | None = None, on_event: EventCb | None = None) -> ExperimentRunner:
    """Re-grade stored transcripts of an experiment with (possibly changed) graders - no agent run."""
    from eval_harness.storage.repositories import experiments

    src = experiments.get(experiment_id)
    if src is None:
        raise KeyError(f"experiment '{experiment_id}' not found")
    suite = load_suite(suite_name or src.suite)
    if graders:
        suite = suite.model_copy(update={"graders": [GraderSpec.model_validate(g) for g in graders]})
    stored = task_snapshots.for_experiment(experiment_id)
    tasks = list(stored.values())
    k = src.summary.get("pass_rates", {}).get("k", suite.run.k)
    suite = suite.model_copy(update={"target": "replay", "run": suite.run.model_copy(update={"k": k})})
    target = target_registry.get("replay").create(suite, source_experiment_id=experiment_id)
    return ExperimentRunner(suite, tasks, target, name=name or f"regrade-{src.name}", on_event=on_event,
                            hooks=default_hooks(), extra_snapshot={"regrade_of": experiment_id})

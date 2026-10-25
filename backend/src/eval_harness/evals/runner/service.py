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


MODE_OF_TARGET = {"local_agent": "live", "multiturn_sim": "multiturn", "trace": "trace", "trace_source": "trace",
                  "replay": "replay"}
NEEDS_NO_AGENT = ("trace", "replay")  # modes/targets that grade stored transcripts


class CapabilityError(ValueError):
    """The chosen variant cannot do what the run asks (refused before anything runs)."""


def resolve_run(suite: Suite, ov: dict[str, Any]) -> tuple[Suite, str, dict[str, Any]]:
    """Which variant runs, with which target, in which mode. Order (keeps every pre-profiles run identical):
    an explicit ``target`` override > a ``mode`` (override, then suite) > the suite's explicit ``target:`` >
    the variant's own target. Returns the updated suite, the target name and snapshot facts."""
    from eval_harness.agent.config import AGENT_TARGETS
    from eval_harness.evals.targets.base import target_capabilities
    from eval_harness.profiles import VariantNotFound, resolve_variant

    explicit_agent = suite.agent if "agent" in suite.model_fields_set else None
    ref = ov.get("variant") or ov.get("agent") or suite.variant or explicit_agent
    mode = ov.get("mode") or suite.mode
    missing: VariantNotFound | None = None
    try:
        _, variant = resolve_variant(ref)
    except VariantNotFound as e:
        variant, missing = None, e  # only an error if the run actually needs the agent (below)

    if ov.get("target"):
        target_name = ov["target"]
    elif mode:
        if mode in NEEDS_NO_AGENT:
            target_name = mode
        elif variant is None:
            raise missing or CapabilityError(f"mode '{mode}' needs a variant to run")
        elif mode == "live":
            target_name = variant.target
        elif variant.target in AGENT_TARGETS:  # multiturn around an in-process agent
            target_name = "multiturn_sim"
        else:
            raise CapabilityError(f"variant '{variant.name}' (target {variant.target}) cannot run multi-turn "
                                  f"conversations here ({'no chat capability' if 'chat' not in target_capabilities(variant.target) else 'not supported for this target yet'})")
    elif "target" in suite.model_fields_set:
        target_name = suite.target
    else:
        target_name = variant.target if variant else suite.target

    if target_name in AGENT_TARGETS and variant is None and ref:
        suite = suite.model_copy(update={"agent": ref})  # target.create raises the usual "agent config not found"
    caps = target_capabilities(target_name)
    if caps is not None and target_name not in NEEDS_NO_AGENT:  # undeclared (pre-profiles) targets: not gated
        what = variant.name if variant else target_name
        if "rerun" not in caps:
            raise CapabilityError(f"variant '{what}' (target {target_name}) cannot be run from the lab; "
                                  "use mode 'trace' to grade its logged runs")
        if suite.run.tool_mode != "live" and "record_replay" not in caps:
            raise CapabilityError(f"tool mode '{suite.run.tool_mode}' needs the record_replay capability, "
                                  f"which target {target_name} does not have")
    if variant is not None and target_name in AGENT_TARGETS:
        suite = suite.model_copy(update={"agent": variant.name})
    suite = suite.model_copy(update={"target": target_name})
    facts = {"variant": variant.name if variant else None, "mode": mode or MODE_OF_TARGET.get(target_name, "live"),
             "capabilities": sorted(caps) if caps is not None else None}
    return suite, target_name, facts


def check_task_needs(tasks: list[Task], target_name: str) -> None:
    from eval_harness.evals.targets.base import target_capabilities

    caps = target_capabilities(target_name)
    faulted = [t.id for t in tasks if t.setup.fault_profile]
    if faulted and caps is not None and target_name not in NEEDS_NO_AGENT and "fault_injection" not in caps:
        raise CapabilityError(f"tasks {faulted[:5]} inject tool faults, which target {target_name} cannot do; "
                              "isolate failures in a staging environment instead")


def prepare_runner(suite_name: str, *, overrides: dict[str, Any] | None = None, name: str | None = None,
                   on_event: EventCb | None = None, hooks: list[RunnerHook] | None = None,
                   tasks: list[Task] | None = None) -> ExperimentRunner:
    """Build a runner. ``overrides`` may set: k, concurrency, tool_mode, variant (or legacy agent),
    mode (or legacy target), max_tasks, target_options (dict), graders (list[GraderSpec dict]), datasets
    (list of groups/paths) - the same knobs the UI exposes. ``datasets`` uses the suite as a template
    (graders, mode, variant) for other data, and drops the suite's tag/kind filters, which were written
    for its own datasets. A run the variant cannot support raises :class:`CapabilityError` up front."""
    ov = dict(overrides or {})
    suite: Suite = load_suite(suite_name)
    if ov.get("datasets"):
        suite = suite.model_copy(update={"datasets": list(ov["datasets"]), "include_tags": [],
                                         "exclude_tags": [], "kinds": []})
    run_over = {k: ov[k] for k in ("k", "concurrency", "tool_mode", "timeout_s", "max_tasks", "fail_fast")
                if ov.get(k) is not None}
    suite = suite.model_copy(update={
        "run": suite.run.model_copy(update=run_over),
        **({"graders": [GraderSpec.model_validate(g) for g in ov["graders"]]} if ov.get("graders") else {}),
    })
    suite, target_name, facts = resolve_run(suite, ov)
    the_tasks = tasks if tasks is not None else suite_tasks(suite)
    if run_over.get("max_tasks"):
        the_tasks = the_tasks[: run_over["max_tasks"]]
    if not the_tasks:
        raise ValueError(f"suite '{suite_name}' selects no tasks"
                         + (f" from datasets {suite.datasets}" if ov.get("datasets") else ""))
    check_task_needs(the_tasks, target_name)
    target = target_registry.get(target_name).create(suite, **(ov.get("target_options") or {}))
    return ExperimentRunner(suite, the_tasks, target, name=name, on_event=on_event,
                            hooks=hooks if hooks is not None else default_hooks(), extra_snapshot=facts)


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

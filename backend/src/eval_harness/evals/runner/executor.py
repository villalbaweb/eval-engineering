"""Runs an experiment: suite x target x k trials, graded, stored, summarized."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import subprocess
import time
from collections.abc import Callable
from typing import Any

from eval_harness.core.ids import new_id, utcnow
from eval_harness.core.settings import REPO_ROOT, get_settings
from eval_harness.evals.domain.experiment import Experiment
from eval_harness.evals.domain.suite import Suite
from eval_harness.evals.domain.task import Task
from eval_harness.evals.domain.trial import Trial
from eval_harness.evals.graders.base import GradeContext, GraderPipeline
from eval_harness.evals.metrics.registry import summarize
from eval_harness.evals.runner.hooks import RunnerHook
from eval_harness.evals.targets.base import Target, TrialInfo
from eval_harness.llm.settings import is_self_judged, judge_configured, resolve_role
from eval_harness.storage.repositories import experiments, task_snapshots
from eval_harness.storage.repositories import trials as trial_repo

log = logging.getLogger(__name__)
EventCb = Callable[[dict[str, Any]], None]


def git_sha() -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO_ROOT, capture_output=True,
                              text=True, timeout=5).stdout.strip() or None
    except Exception:  # noqa: BLE001
        return None


def tasks_hash(tasks: list[Task]) -> str:
    blob = json.dumps([t.model_dump(mode="json") for t in tasks], sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:12]


class ExperimentRunner:
    def __init__(self, suite: Suite, tasks: list[Task], target: Target, *, name: str | None = None,
                 hooks: list[RunnerHook] | None = None, on_event: EventCb | None = None,
                 extra_snapshot: dict[str, Any] | None = None, experiment_id: str | None = None):
        self.suite, self.tasks, self.target = suite, tasks, target
        self.hooks = hooks or []
        self.on_event = on_event or (lambda e: None)
        self.pipeline = GraderPipeline(suite.graders, fail_fast=suite.run.fail_fast)
        self.cancel_event = asyncio.Event()
        stamp = utcnow().strftime("%m%d-%H%M%S")
        self.exp = Experiment(
            id=experiment_id or new_id("exp_"), name=name or f"{suite.name}-{stamp}", suite=suite.name,
            target=target.type, total_trials=len(tasks) * suite.run.k,
            snapshot=self._snapshot(extra_snapshot or {}))

    # ------------------------------------------------------------------
    def _snapshot(self, extra: dict[str, Any]) -> dict[str, Any]:
        roles = {r: resolve_role(r).model_dump() for r in ("agent", "judge", "simulator")}
        return {
            "suite": self.suite.model_dump(mode="json"),
            "target": self.target.snapshot(),
            "models": roles,
            "judge_configured": judge_configured(),
            "self_judged": is_self_judged() and judge_configured(),
            "tasks_hash": tasks_hash(self.tasks),
            "n_tasks": len(self.tasks),
            "git_sha": git_sha(),
            "langsmith": get_settings().langsmith_enabled,
            **extra,
        }

    def _emit(self, type_: str, **data: Any) -> None:
        self.on_event({"type": type_, "experiment_id": self.exp.id, **data})

    def _call_hooks(self, name: str, *args: Any) -> None:
        for h in self.hooks:
            try:
                getattr(h, name)(*args)
            except Exception:  # noqa: BLE001
                log.exception("hook %s.%s failed", type(h).__name__, name)

    def cancel(self) -> None:
        self.cancel_event.set()

    # ------------------------------------------------------------------
    async def _run_trial(self, task: Task, index: int, sem: asyncio.Semaphore) -> Trial | None:
        async with sem:
            if self.cancel_event.is_set():
                return None
            trial = Trial(id=new_id("t_"), experiment_id=self.exp.id, task_id=task.id, index=index)
            t0 = time.perf_counter()
            info = TrialInfo(self.exp.id, trial.id, index, self.suite.name)
            self._emit("trial_start", task_id=task.id, index=index)
            transcript, outcome = await self.target.run(task, self.suite.run, info)
            trial.transcript, trial.outcome = transcript, outcome
            if outcome.status == "ok":
                trial.grades = await self.pipeline.run(
                    GradeContext(task, transcript, outcome, trial.id, self.exp.id))
            trial.duration_s = round(time.perf_counter() - t0, 3)
            trial_repo.save(trial)
            self.exp.done_trials += 1
            self._call_hooks("on_trial_end", self.exp, trial, task)
            self._emit("trial_done", task_id=task.id, index=index, trial_id=trial.id, passed=trial.passed,
                       status=outcome.status, done=self.exp.done_trials, total=self.exp.total_trials)
            return trial

    async def run(self) -> Experiment:
        exp, run = self.exp, self.suite.run
        exp.status = "running"
        experiments.save(exp)
        task_snapshots.save_many(exp.id, self.tasks)
        self._emit("experiment_started", name=exp.name, total=exp.total_trials)
        self._call_hooks("on_experiment_start", exp, self.tasks)
        sem = asyncio.Semaphore(max(1, run.concurrency))
        try:
            results = await asyncio.gather(*(self._run_trial(t, i, sem) for t in self.tasks for i in range(run.k)))
            done = [t for t in results if t is not None]
            by_task = {t.id: t for t in self.tasks}
            exp.summary = summarize(done, by_task, run.k)
            exp.status = "cancelled" if self.cancel_event.is_set() else "completed"
            exp.finished_at = utcnow()
            experiments.save(exp)
            self._call_hooks("on_experiment_end", exp, done, by_task)
            experiments.save(exp)  # hooks may add e.g. langsmith_url
        except Exception as e:  # noqa: BLE001
            log.exception("experiment failed")
            exp.status, exp.error, exp.finished_at = "failed", f"{type(e).__name__}: {e}", utcnow()
            experiments.save(exp)
        self._emit("experiment_done", status=exp.status,
                   pass_rate=exp.summary.get("pass_rates", {}).get("trial_pass_rate"))
        return exp

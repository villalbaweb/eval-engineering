"""Lifecycle hooks: exporters and integrations subscribe without touching the runner."""

from __future__ import annotations

from eval_harness.evals.domain.experiment import Experiment
from eval_harness.evals.domain.task import Task
from eval_harness.evals.domain.trial import Trial


class RunnerHook:
    """Override any subset. Exceptions raised here are logged and swallowed by the runner."""

    def on_experiment_start(self, exp: Experiment, tasks: list[Task]) -> None: ...

    def on_trial_end(self, exp: Experiment, trial: Trial, task: Task) -> None: ...

    def on_experiment_end(self, exp: Experiment, trials: list[Trial], tasks: dict[str, Task]) -> None: ...

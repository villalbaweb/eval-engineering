"""Re-use stored transcripts instead of running the agent.

``replay``  - transcripts of a previous experiment (re-grade with new/changed graders; the answer to
              criteria drift: iterate on graders cheaply without re-running the agent).
``trace``   - logged transcripts embedded in the task (``task.metadata['transcript']``), e.g. imported
              traces (online-style evaluation of logged traffic).
"""

from __future__ import annotations

from typing import Any

from eval_harness.evals.domain.outcome import Outcome
from eval_harness.evals.domain.suite import RunSettings, Suite
from eval_harness.evals.domain.task import Task
from eval_harness.evals.domain.transcript import Transcript
from eval_harness.evals.targets.base import Target, TrialInfo, register_target
from eval_harness.storage.repositories import trials as trial_repo


@register_target("replay")
class ReplayTarget(Target):
    def __init__(self, source_experiment_id: str):
        self.source = source_experiment_id
        self._by_key = {(t.task_id, t.index): t for t in trial_repo.for_experiment(source_experiment_id)}
        if not self._by_key:
            raise ValueError(f"experiment '{source_experiment_id}' has no stored trials")

    @classmethod
    def create(cls, suite: Suite, *, source_experiment_id: str | None = None, **_: Any):
        if not source_experiment_id:
            raise ValueError("replay target needs source_experiment_id")
        return cls(source_experiment_id)

    def snapshot(self) -> dict[str, Any]:
        return {"type": self.type, "source_experiment_id": self.source}

    async def run(self, task: Task, run: RunSettings, info: TrialInfo) -> tuple[Transcript, Outcome]:
        t = self._by_key.get((task.id, info.index)) or self._by_key.get((task.id, 0))
        if t is None:
            return Transcript(), Outcome(status="error", error=f"no stored trial for task {task.id}")
        return t.transcript, t.outcome


@register_target("trace")
class TraceTarget(Target):
    """Grade logged traces as they are; nothing is re-run."""

    def snapshot(self) -> dict[str, Any]:
        return {"type": self.type}

    async def run(self, task: Task, run: RunSettings, info: TrialInfo) -> tuple[Transcript, Outcome]:
        raw = task.metadata.get("transcript")
        if not raw:
            return Transcript(), Outcome(status="error", error="task has no logged transcript")
        t = Transcript.model_validate(raw)
        return t, Outcome(final_answer=t.final_answer, status="ok")

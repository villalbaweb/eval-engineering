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
    capabilities = frozenset()  # grades stored transcripts; runs nothing

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

    capabilities = frozenset()

    def snapshot(self) -> dict[str, Any]:
        return {"type": self.type}

    async def run(self, task: Task, run: RunSettings, info: TrialInfo) -> tuple[Transcript, Outcome]:
        raw = task.metadata.get("transcript")
        if not raw:
            return Transcript(), Outcome(status="error", error="task has no logged transcript")
        t = Transcript.model_validate(raw)
        if not t.tool_calls and any(m.get("tool_calls") for m in t.messages):
            # messages only (e.g. a hand-written dataset of another agent): derive tool calls, errors and
            # skills with the agent profile's conventions, exactly like the trace importer does
            from eval_harness.evals.data_sources.traces.base import transcript_from_messages
            from eval_harness.profiles import active_profile

            derived = transcript_from_messages(t.messages, conventions=active_profile().conventions, **t.meta)
            t = t.model_copy(update={"tool_calls": derived.tool_calls, "skills_loaded": derived.skills_loaded})
        return t, Outcome(final_answer=t.final_answer, status="ok")


@register_target("trace_source")
class TraceSourceTarget(TraceTarget):
    """Target of a read-only variant (e.g. ``prod-traces``): the agent cannot be called from the lab,
    only its logged runs are graded. Supports no capabilities, so live/multiturn runs, the Playground
    and traffic simulation are refused with a reason."""

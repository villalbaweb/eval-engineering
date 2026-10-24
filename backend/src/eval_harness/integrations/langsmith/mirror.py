"""Mirror every experiment into LangSmith: a dataset + an experiment project whose runs carry the
grades as feedback. The native runner stays authoritative; this gives you LangSmith's compare view."""

from __future__ import annotations

import logging
import uuid

from eval_harness.evals.domain.experiment import Experiment
from eval_harness.evals.domain.task import Task
from eval_harness.evals.domain.trial import Trial
from eval_harness.evals.runner.hooks import RunnerHook
from eval_harness.integrations.langsmith import datasets
from eval_harness.integrations.langsmith.client import enabled, get_client

log = logging.getLogger(__name__)


class ExperimentMirror(RunnerHook):
    def on_experiment_end(self, exp: Experiment, trials: list[Trial], tasks: dict[str, Task]) -> None:
        if not enabled() or exp.snapshot.get("target", {}).get("type") == "trace":
            return
        try:
            self._mirror(exp, trials, tasks)
        except Exception as e:  # noqa: BLE001
            log.warning("LangSmith mirror failed: %s: %s", type(e).__name__, e)

    def _mirror(self, exp: Experiment, trials: list[Trial], tasks: dict[str, Task]) -> None:
        c = get_client()
        pushed = datasets.push_tasks(exp.suite, list(tasks.values())) or {}
        ids = pushed.get("example_ids", {})
        project = c.create_project(
            project_name=exp.name, reference_dataset_id=pushed.get("dataset_id"),
            description=f"eval-harness experiment {exp.id}",
            metadata={"experiment_id": exp.id, "suite": exp.suite, "git_sha": exp.snapshot.get("git_sha"),
                      "model": exp.snapshot.get("models", {}).get("agent", {}).get("model")})
        # LangSmith deprecates feedback without a session (project) / trace id; every mirrored run is a root run,
        # so its trace id is its own run id (added per run below).
        session_id = getattr(project, "id", None)
        for t in trials:
            run_id = uuid.uuid4()
            scope = {"trace_id": run_id, **({"session_id": session_id} if session_id else {})}
            tr = t.transcript
            c.create_run(
                id=run_id, name=t.task_id, run_type="chain", project_name=exp.name,
                inputs=tasks[t.task_id].input if t.task_id in tasks else {},
                outputs={"answer": tr.final_answer, "messages": tr.messages, "skills_loaded": tr.skills_loaded,
                         "tool_calls": [x.name for x in tr.tool_calls]},
                error=t.outcome.error, start_time=t.started_at,
                end_time=t.started_at, reference_example_id=ids.get(t.task_id),
                extra={"metadata": {"trial_id": t.id, "trial_index": t.index,
                                    "trace_run_id": tr.meta.get("langsmith_run_id")}},
            )
            c.update_run(run_id, end_time=t.started_at, outputs={"answer": tr.final_answer})
            for g in t.grades:
                if g.skipped or g.score is None:
                    continue
                c.create_feedback(run_id, key=g.grader, score=g.score, comment=g.rationale[:500], **scope)
            c.create_feedback(run_id, key="trial_passed", score=1.0 if t.passed else 0.0, **scope)
        exp.langsmith_url = getattr(project, "url", None) or None

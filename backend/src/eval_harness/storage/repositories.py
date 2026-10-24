"""Repositories: the only code that talks to the database."""

from __future__ import annotations

from sqlmodel import select

from eval_harness.evals.domain.experiment import Experiment
from eval_harness.evals.domain.task import Task
from eval_harness.evals.domain.trial import Trial
from eval_harness.storage.db import AnnotationRow, ExperimentRow, TaskRow, TrialRow, session_scope


class ExperimentRepo:
    def save(self, exp: Experiment) -> None:
        with session_scope() as s:
            row = s.get(ExperimentRow, exp.id)
            payload = exp.model_dump_json()
            if row:
                row.status, row.payload = exp.status, payload
            else:
                s.add(ExperimentRow(id=exp.id, name=exp.name, suite=exp.suite, status=exp.status,
                                    created_at=exp.created_at, payload=payload))

    def get(self, exp_id: str) -> Experiment | None:
        with session_scope() as s:
            row = s.get(ExperimentRow, exp_id)
            return Experiment.model_validate_json(row.payload) if row else None

    def latest_id(self) -> str | None:
        with session_scope() as s:
            row = s.exec(select(ExperimentRow).order_by(ExperimentRow.created_at.desc())).first()
            return row.id if row else None

    def list(self, limit: int = 100) -> list[Experiment]:
        with session_scope() as s:
            rows = s.exec(select(ExperimentRow).order_by(ExperimentRow.created_at.desc()).limit(limit)).all()
            return [Experiment.model_validate_json(r.payload) for r in rows]


class TrialRepo:
    def save(self, trial: Trial) -> None:
        with session_scope() as s:
            row = s.get(TrialRow, trial.id)
            payload = trial.model_dump_json()
            if row:
                row.passed, row.payload = trial.passed, payload
            else:
                s.add(TrialRow(id=trial.id, experiment_id=trial.experiment_id, task_id=trial.task_id,
                               passed=trial.passed, payload=payload))

    def get(self, trial_id: str) -> Trial | None:
        with session_scope() as s:
            row = s.get(TrialRow, trial_id)
            return Trial.model_validate_json(row.payload) if row else None

    def latest(self) -> Trial | None:
        with session_scope() as s:
            row = s.exec(select(TrialRow).order_by(TrialRow.created_at.desc())).first()
            return Trial.model_validate_json(row.payload) if row else None

    def for_experiment(self, exp_id: str) -> list[Trial]:
        with session_scope() as s:
            rows = s.exec(select(TrialRow).where(TrialRow.experiment_id == exp_id)).all()
            return [Trial.model_validate_json(r.payload) for r in rows]


class TaskSnapshotRepo:
    def save_many(self, exp_id: str, tasks: list[Task]) -> None:
        with session_scope() as s:
            for t in tasks:
                s.merge(TaskRow(experiment_id=exp_id, task_id=t.id, payload=t.model_dump_json()))

    def for_experiment(self, exp_id: str) -> dict[str, Task]:
        with session_scope() as s:
            rows = s.exec(select(TaskRow).where(TaskRow.experiment_id == exp_id)).all()
            return {r.task_id: Task.model_validate_json(r.payload) for r in rows}


class AnnotationRepo:
    def upsert(self, trial_id: str, experiment_id: str, good: bool, failure_tags: list[str],
               note: str) -> AnnotationRow:
        with session_scope() as s:
            row = s.exec(select(AnnotationRow).where(AnnotationRow.trial_id == trial_id)).first()
            if row:
                row.good, row.failure_tags, row.note = good, ",".join(failure_tags), note
            else:
                row = AnnotationRow(trial_id=trial_id, experiment_id=experiment_id, good=good,
                                    failure_tags=",".join(failure_tags), note=note)
                s.add(row)
            s.flush()
            s.refresh(row)
            return row

    def all(self, experiment_id: str | None = None) -> list[AnnotationRow]:
        with session_scope() as s:
            q = select(AnnotationRow)
            if experiment_id:
                q = q.where(AnnotationRow.experiment_id == experiment_id)
            return list(s.exec(q).all())


experiments = ExperimentRepo()
trials = TrialRepo()
task_snapshots = TaskSnapshotRepo()
annotations = AnnotationRepo()

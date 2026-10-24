from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from functools import lru_cache

from sqlalchemy import Column, Text
from sqlmodel import Field, Session, SQLModel, create_engine

from eval_harness.core.ids import utcnow
from eval_harness.core.settings import get_settings


class ExperimentRow(SQLModel, table=True):
    __tablename__ = "experiments"
    id: str = Field(primary_key=True)
    name: str = Field(index=True)
    suite: str = Field(index=True)
    status: str = Field(default="pending", index=True)
    created_at: datetime = Field(default_factory=utcnow, index=True)
    payload: str = Field(sa_column=Column(Text))  # Experiment JSON


class TrialRow(SQLModel, table=True):
    __tablename__ = "trials"
    id: str = Field(primary_key=True)
    experiment_id: str = Field(index=True)
    task_id: str = Field(index=True)
    passed: bool = False
    created_at: datetime = Field(default_factory=utcnow)
    payload: str = Field(sa_column=Column(Text))  # Trial JSON


class TaskRow(SQLModel, table=True):
    """Snapshot of the task as it was when the experiment ran (datasets may change later)."""

    __tablename__ = "experiment_tasks"
    experiment_id: str = Field(primary_key=True)
    task_id: str = Field(primary_key=True)
    payload: str = Field(sa_column=Column(Text))


class AnnotationRow(SQLModel, table=True):
    """Human label on a trial (ground truth for grader calibration)."""

    __tablename__ = "annotations"
    id: int | None = Field(default=None, primary_key=True)
    trial_id: str = Field(index=True)
    experiment_id: str = Field(index=True)
    good: bool
    failure_tags: str = ""  # comma separated
    note: str = ""
    created_at: datetime = Field(default_factory=utcnow)


@lru_cache
def get_engine():
    url = get_settings().db_url
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine = create_engine(url, connect_args=connect_args)
    SQLModel.metadata.create_all(engine)
    return engine


@contextmanager
def session_scope() -> Iterator[Session]:
    # expire_on_commit=False: repositories hand out rows that outlive the session
    with Session(get_engine(), expire_on_commit=False) as s:
        yield s
        s.commit()


def reset_engine_cache() -> None:
    get_engine.cache_clear()

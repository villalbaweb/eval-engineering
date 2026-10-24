from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from eval_harness.core.ids import utcnow


class Experiment(BaseModel):
    id: str
    name: str
    suite: str
    target: str = "local_agent"
    status: Literal["pending", "running", "completed", "failed", "cancelled"] = "pending"
    created_at: datetime = Field(default_factory=utcnow)
    finished_at: datetime | None = None
    # immutable snapshot of everything that explains the results
    snapshot: dict[str, Any] = Field(default_factory=dict)
    total_trials: int = 0
    done_trials: int = 0
    summary: dict[str, Any] = Field(default_factory=dict)
    langsmith_url: str | None = None
    error: str | None = None

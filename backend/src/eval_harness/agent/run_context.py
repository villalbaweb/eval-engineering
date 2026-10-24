"""Per-run mutable state shared by the middleware of ONE agent invocation."""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from eval_harness.evals.domain.transcript import ToolCallRecord
from eval_harness.skills.loader import SkillSpec


@dataclass
class RunContext:
    tool_mode: str = "live"  # live | record | replay
    cassette: str | None = None  # cassette name (file in evals/cassettes)
    fault_profile: str | None = None
    skills: list[SkillSpec] = field(default_factory=list)
    on_event: Callable[[dict[str, Any]], None] | None = None  # live UI streaming

    # collected during the run
    tool_records: list[ToolCallRecord] = field(default_factory=list)
    skills_loaded: list[str] = field(default_factory=list)
    guardrail_events: list[dict[str, Any]] = field(default_factory=list)
    notes: dict[str, dict[str, Any]] = field(default_factory=dict)  # tool_call_id -> annotations
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def note(self, tool_call_id: str, **kv: Any) -> None:
        with self._lock:
            self.notes.setdefault(tool_call_id, {}).update(kv)

    def emit(self, type_: str, **data: Any) -> None:
        if self.on_event:
            self.on_event({"type": type_, **data})

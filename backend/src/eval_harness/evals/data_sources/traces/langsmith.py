from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from eval_harness.core.settings import get_settings
from eval_harness.evals.data_sources.traces.base import (
    TraceAdapter,
    TraceRecord,
    normalize_messages,
    register_adapter,
    transcript_from_messages,
)
from eval_harness.evals.domain.profile import Conventions


def run_to_record(run: Any, feedback: dict[str, Any] | None = None,
                  conventions: Conventions | None = None) -> TraceRecord | None:
    """A LangSmith root run of the agent -> TraceRecord (None if it has no messages). The transcript is
    read with the agent profile's ``conventions`` (skills, tool errors)."""
    inputs, outputs = run.inputs or {}, run.outputs or {}
    statuses: dict[str, str] = {}
    out_msgs = normalize_messages(outputs.get("messages") or [], statuses)
    in_msgs = normalize_messages(inputs.get("messages") or [])
    if not out_msgs and not in_msgs:
        return None
    msgs = out_msgs or in_msgs  # agent output state contains the whole conversation
    meta = (getattr(run, "extra", None) or {}).get("metadata", {}) or {}
    t = transcript_from_messages(msgs, conventions=conventions, statuses=statuses, langsmith_run_id=str(run.id))
    started, ended = getattr(run, "start_time", None), getattr(run, "end_time", None)
    if started and ended:
        t.latency_s = round((ended - started).total_seconds(), 3)
    return TraceRecord(
        id=str(run.id), source=meta.get("source", "external"),
        created_at=started.isoformat() if started else None, input_messages=in_msgs or msgs[:1],
        transcript=t, status="error" if getattr(run, "error", None) else "ok", error=getattr(run, "error", None),
        feedback=feedback or {})


@register_adapter("langsmith")
class LangSmithAdapter(TraceAdapter):
    """Reads root runs of the agent from the LangSmith tracing project (Playground chats, simulated
    traffic and experiment trials all land there, distinguished by ``metadata.source``)."""

    def fetch(self, *, limit: int = 50, source: str | None = None, errors_only: bool = False,
              path: str | None = None, project: str | None = None, hours: int = 72,
              conventions: Conventions | None = None, **opts: Any) -> list[TraceRecord]:
        from eval_harness.integrations.langsmith.client import enabled, get_client

        if not enabled():
            raise RuntimeError("LangSmith is not enabled (set LANGSMITH_API_KEY and LANGSMITH_TRACING=true)")
        c = get_client()
        filters = []
        if source:
            filters.append(f'and(eq(metadata_key, "source"), eq(metadata_value, "{source}"))')
        if errors_only:
            filters.append("eq(error, true)")
        flt = filters[0] if len(filters) == 1 else (f"and({', '.join(filters)})" if filters else None)
        runs = c.list_runs(project_name=project or get_settings().langsmith_project, is_root=True, limit=limit,
                           start_time=datetime.now(UTC) - timedelta(hours=hours), filter=flt)
        out = []
        for r in runs:
            fb = {}
            try:
                for f in c.list_feedback(run_ids=[r.id]):
                    if f.key == "thumbs":
                        fb["thumbs"] = int(f.score or 0)
            except Exception:  # noqa: BLE001
                pass
            rec = run_to_record(r, fb, conventions)
            if rec:
                out.append(rec)
        return out

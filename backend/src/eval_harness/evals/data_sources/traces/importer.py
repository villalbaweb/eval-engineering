from __future__ import annotations

from typing import Any

from eval_harness.evals.data_sources import quality, review
from eval_harness.evals.data_sources.traces.base import TraceRecord, trace_adapter_registry
from eval_harness.evals.domain.task import Task


def scrub_record(rec: TraceRecord) -> TraceRecord:
    for m in rec.transcript.messages:
        if isinstance(m.get("content"), str):
            m["content"] = quality.scrub_pii(m["content"])
    for tc in rec.transcript.tool_calls:
        tc.result = quality.scrub_pii(tc.result)
    for m in rec.input_messages:
        if isinstance(m.get("content"), str):
            m["content"] = quality.scrub_pii(m["content"])
    return rec


def record_to_task(rec: TraceRecord, adapter: str) -> Task:
    """The user's input becomes the task input; the logged transcript rides along in metadata so the
    'trace' target can grade it without re-running anything. Expectations are left empty: add them
    during review once you decided what the right behaviour was."""
    users = [m for m in rec.input_messages if m.get("role") == "user"] or rec.input_messages[:1]
    first_turn = users[:1]
    tags = ["trace", rec.source] + (["negative-feedback"] if rec.feedback.get("thumbs") == 0 else []) + (
        ["error"] if rec.status != "ok" else [])
    return Task(
        id=f"trace-{rec.id.replace('-', '')[:12]}", kind="regression", tags=tags,
        input={"messages": [{"role": "user", "content": first_turn[0]["content"]}] if first_turn else []},
        source=f"traces:{adapter}",
        metadata={"transcript": rec.transcript.model_dump(mode="json"), "trace_id": rec.id,
                  "feedback": rec.feedback, "trace_source": rec.source})


def import_traces(adapter: str = "langsmith", *, limit: int = 50, source: str | None = None,
                  errors_only: bool = False, path: str | None = None, **opts: Any) -> dict[str, Any]:
    records = trace_adapter_registry.get(adapter)().fetch(limit=limit, source=source, errors_only=errors_only,
                                                           path=path, **opts)
    tasks = [record_to_task(scrub_record(r), adapter) for r in records if r.input_messages]
    res = review.save_candidates(tasks)
    res["fetched"] = len(records)
    return res

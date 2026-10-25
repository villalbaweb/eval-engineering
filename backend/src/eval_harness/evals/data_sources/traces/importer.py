from __future__ import annotations

from typing import Any

from eval_harness.evals.data_sources import quality, review
from eval_harness.evals.data_sources.traces.base import (
    TraceRecord,
    trace_adapter_registry,
    transcript_from_messages,
)
from eval_harness.evals.domain.profile import Conventions
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


def apply_conventions(rec: TraceRecord, conv: Conventions) -> TraceRecord:
    """Records that carry only messages (e.g. an external agent's JSONL export) get their tool calls,
    errors and skills derived with the profile's conventions. Records that already have tool calls (the
    lab's own traffic files, LangSmith imports) are kept exactly as they are."""
    t = rec.transcript
    has_calls = any(m.get("tool_calls") for m in t.messages)
    if t.messages and has_calls and not t.tool_calls:
        rebuilt = transcript_from_messages(t.messages, conventions=conv, **t.meta)
        rebuilt.usage, rebuilt.latency_s, rebuilt.model_slug = t.usage, t.latency_s, t.model_slug
        rec = rec.model_copy(update={"transcript": rebuilt})
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
    """Fetch logged runs of the ACTIVE profile's agent, read them with its conventions, queue them for
    review. Unset options fall back to the profile's ``traces:`` settings (where its traces live)."""
    from eval_harness.core.settings import get_settings
    from eval_harness.profiles import active_profile

    prof = active_profile()
    src = prof.traces
    if path is None and src.path:
        path = str((get_settings().profile_dir / src.path).resolve())
    if source is None and isinstance(src.filters.get("source"), str):
        source = src.filters["source"]
    if src.project and "project" not in opts:
        opts["project"] = src.project
    if src.window_hours != 72 and "hours" not in opts:
        opts["hours"] = src.window_hours
    records = trace_adapter_registry.get(adapter)().fetch(limit=limit, source=source, errors_only=errors_only,
                                                           path=path, conventions=prof.conventions, **opts)
    records = [apply_conventions(r, prof.conventions) for r in records]
    tasks = [record_to_task(scrub_record(r), adapter) for r in records if r.input_messages]
    res = review.save_candidates(tasks)
    res["fetched"] = len(records)
    return res


def default_adapter() -> str:
    """The active profile's trace adapter, else LangSmith when enabled, else local JSONL files."""
    from eval_harness.integrations.langsmith.client import enabled
    from eval_harness.profiles import active_profile

    return active_profile().traces.adapter or ("langsmith" if enabled() else "jsonl")

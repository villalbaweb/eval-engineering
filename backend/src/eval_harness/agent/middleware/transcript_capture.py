"""Records every tool call (args, result, latency, errors) into the RunContext.

Also turns raised tool exceptions into error ``ToolMessage`` s so the agent can recover and the
failure shows up in the transcript instead of crashing the run.
"""

from __future__ import annotations

import time

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import ToolMessage

from eval_harness.agent.middleware.registry import middleware_registry
from eval_harness.agent.run_context import RunContext
from eval_harness.evals.domain.transcript import ToolCallRecord


def _content_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in content)
    return str(content)


class TranscriptCapture(AgentMiddleware):
    def __init__(self, ctx: RunContext):
        super().__init__()
        self.ctx = ctx

    @property
    def name(self) -> str:
        return "transcript_capture"

    def wrap_tool_call(self, request, handler):
        call = request.tool_call
        t0 = time.perf_counter()
        self.ctx.emit("tool_start", name=call["name"], args=call["args"], id=call["id"])
        exc: Exception | None = None
        try:
            result = handler(request)
        except Exception as e:  # noqa: BLE001 - surfaced to the agent as an error message
            exc = e
            result = ToolMessage(content=f"ERROR: {type(e).__name__}: {e}", tool_call_id=call["id"],
                                 name=call["name"], status="error")
        latency = time.perf_counter() - t0
        text = _content_text(getattr(result, "content", ""))
        is_error = exc is not None or getattr(result, "status", None) == "error" or text.startswith("ERROR")
        notes = self.ctx.notes.get(call["id"], {})
        rec = ToolCallRecord(id=call["id"], name=call["name"], args=call["args"], result=text,
                             error=is_error, latency_s=round(latency, 4),
                             replayed=bool(notes.get("replayed")), injected_fault=notes.get("fault"))
        self.ctx.tool_records.append(rec)
        self.ctx.emit("tool_end", **rec.model_dump())
        return result


@middleware_registry.register("transcript_capture")
def build(ctx: RunContext) -> TranscriptCapture:
    return TranscriptCapture(ctx)

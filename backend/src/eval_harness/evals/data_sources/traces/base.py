"""Trace adapters: normalize logged agent runs from any source into :class:`TraceRecord`."""

from __future__ import annotations

from typing import Any, ClassVar

from pydantic import BaseModel, Field

from eval_harness.core.registry import Registry
from eval_harness.evals.domain.profile import Conventions
from eval_harness.evals.domain.transcript import Transcript


class TraceRecord(BaseModel):
    id: str
    source: str = "unknown"  # playground | traffic | experiment | external
    created_at: str | None = None
    input_messages: list[dict[str, Any]] = Field(default_factory=list)
    transcript: Transcript = Field(default_factory=Transcript)
    status: str = "ok"
    error: str | None = None
    feedback: dict[str, Any] = Field(default_factory=dict)  # e.g. {"thumbs": 0}


class TraceAdapter:
    type: ClassVar[str] = ""

    def fetch(self, *, limit: int = 50, source: str | None = None, errors_only: bool = False,
              path: str | None = None, **opts: Any) -> list[TraceRecord]:  # pragma: no cover - interface
        raise NotImplementedError


trace_adapter_registry: Registry[type[TraceAdapter]] = Registry(
    "trace adapter", package="eval_harness.evals.data_sources.traces", entry_point_group="eval_harness.trace_adapters"
)


def register_adapter(type_: str):
    def deco(cls: type[TraceAdapter]) -> type[TraceAdapter]:
        cls.type = type_
        trace_adapter_registry.register(type_)(cls)
        return cls

    return deco


ROLE_BY_TYPE = {"human": "user", "ai": "assistant", "tool": "tool", "system": "system",
                "HumanMessage": "user", "AIMessage": "assistant", "ToolMessage": "tool", "SystemMessage": "system"}


def normalize_messages(raw: list[Any], statuses: dict[str, str] | None = None) -> list[dict[str, Any]]:
    """LangChain-serialized (or OpenAI-style) messages -> OpenAI chat dicts.

    ``statuses``, when given, is filled with ``tool_call_id -> status`` of tool messages (kept out of the
    messages themselves) for profiles whose tool-error convention reads the message status."""
    out: list[dict[str, Any]] = []
    for m in raw or []:
        if not isinstance(m, dict):
            continue
        if m.get("lc") and "kwargs" in m:  # constructor-serialized
            kind = (m.get("id") or ["?"])[-1]
            m = {**m["kwargs"], "type": kind}
        role = m.get("role") or ROLE_BY_TYPE.get(str(m.get("type")), "assistant")
        msg: dict[str, Any] = {"role": role, "content": m.get("content", "")}
        calls = m.get("tool_calls") or []
        if calls:
            import json

            norm = []
            for tc in calls:
                if "function" in tc:
                    norm.append(tc)
                else:
                    norm.append({"id": tc.get("id", ""), "type": "function", "function": {
                        "name": tc.get("name", ""), "arguments": json.dumps(tc.get("args", {}))}})
            msg["tool_calls"] = norm
        if role == "tool":
            msg["tool_call_id"] = m.get("tool_call_id", "")
            if statuses is not None and m.get("status"):
                statuses[msg["tool_call_id"]] = str(m["status"])
        out.append(msg)
    return out


def transcript_from_messages(messages: list[dict[str, Any]], *, conventions: Conventions | None = None,
                             statuses: dict[str, str] | None = None, **meta: Any) -> Transcript:
    """Rebuild tool-call records and the skills list from plain messages, reading them with the agent
    profile's ``conventions`` (default: the lab's own rules)."""
    import json

    from eval_harness.evals.domain.transcript import ToolCallRecord
    from eval_harness.profiles.conventions import skill_from_call, tool_failed

    conv = conventions or Conventions()
    statuses = statuses or {}
    results = {m.get("tool_call_id"): m for m in messages if m.get("role") == "tool"}
    calls, skills = [], []
    for m in messages:
        for tc in m.get("tool_calls") or []:
            fn = tc.get("function", {})
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            res = results.get(tc.get("id"), {})
            text = res.get("content", "") if isinstance(res.get("content"), str) else str(res.get("content", ""))
            calls.append(ToolCallRecord(id=tc.get("id", ""), name=fn.get("name", ""), args=args, result=text,
                                        error=tool_failed(conv, text, statuses.get(tc.get("id", "")))))
            skill = skill_from_call(conv, fn.get("name", ""), args if isinstance(args, dict) else {})
            if skill:
                skills.append(skill)
    return Transcript(messages=messages, tool_calls=calls, skills_loaded=list(dict.fromkeys(skills)), meta=meta)

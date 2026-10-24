"""LangChain messages + RunContext -> normalized :class:`Transcript`."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.messages.utils import convert_to_openai_messages

from eval_harness.agent.run_context import RunContext
from eval_harness.evals.domain.transcript import Transcript, Usage


def _usage(messages: list[BaseMessage]) -> Usage:
    u = Usage()
    for m in messages:
        if not isinstance(m, AIMessage):
            continue
        u.model_calls += 1
        meta = m.usage_metadata or {}
        u.input_tokens += int(meta.get("input_tokens", 0))
        u.output_tokens += int(meta.get("output_tokens", 0))
        u.total_tokens += int(meta.get("total_tokens", 0) or meta.get("input_tokens", 0) + meta.get("output_tokens", 0))
        cost = (m.response_metadata or {}).get("token_usage", {}).get("cost")
        if isinstance(cost, int | float):
            u.cost_usd = (u.cost_usd or 0.0) + float(cost)
    return u


def build_transcript(messages: list[BaseMessage], ctx: RunContext, *, model_slug: str, latency_s: float,
                     extra_meta: dict[str, Any] | None = None) -> Transcript:
    oa = convert_to_openai_messages(messages)
    oa = oa if isinstance(oa, list) else [oa]
    return Transcript(
        messages=oa,
        tool_calls=list(ctx.tool_records),
        skills_loaded=list(ctx.skills_loaded),
        usage=_usage(messages),
        latency_s=round(latency_s, 3),
        model_slug=model_slug,
        meta={"guardrail_events": list(ctx.guardrail_events), **(extra_meta or {})},
    )

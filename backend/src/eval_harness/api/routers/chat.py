"""Playground: chat with the Eval Copilot and watch skills/tools fire live (SSE)."""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from eval_harness.agent.config import load_agent_config
from eval_harness.agent.factory import build_agent
from eval_harness.agent.run_context import RunContext
from eval_harness.agent.transcript_builder import build_transcript
from eval_harness.core.settings import get_settings
from eval_harness.integrations.langsmith.client import get_client, safe

router = APIRouter(tags=["chat"])


class ChatRequest(BaseModel):
    messages: list[dict[str, Any]]  # full history, OpenAI format
    agent: str | None = None  # legacy name of `variant`
    variant: str | None = None  # variant of the active profile (default: the profile's default variant)
    fault_profile: str | None = None


def chat_variant(ref: str | None, *, fault_profile: str | None = None) -> str:
    """The in-process agent config to chat with, or an HTTP 400 explaining why this variant cannot chat."""
    from eval_harness.agent.config import AGENT_TARGETS
    from eval_harness.evals.targets.base import target_capabilities
    from eval_harness.profiles import VariantNotFound, resolve_variant

    try:
        _, v = resolve_variant(ref)
    except VariantNotFound as e:
        raise HTTPException(400, str(e)) from e
    caps = target_capabilities(v.target)
    if caps is not None and "chat" not in caps:
        raise HTTPException(400, f"variant '{v.name}' (target {v.target}) cannot chat: it only has logged runs")
    if v.target not in AGENT_TARGETS:
        raise HTTPException(400, f"chatting with target '{v.target}' is not supported in the Playground yet")
    if fault_profile and caps is not None and "fault_injection" not in caps:
        raise HTTPException(400, f"variant '{v.name}' does not support fault injection")
    return v.name


def _text(content: Any) -> str:
    if isinstance(content, str):
        return content
    return "".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in content or [])


@router.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    from eval_harness.profiles import active_profile_name

    agent_name = chat_variant(req.variant or req.agent, fault_profile=req.fault_profile)
    profile = active_profile_name()
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()
    run_id = str(uuid.uuid4())

    def push(e: dict) -> None:  # called from the agent thread
        loop.call_soon_threadsafe(queue.put_nowait, e)

    def work() -> None:
        try:
            ctx = RunContext(on_event=push, fault_profile=req.fault_profile)
            agent = build_agent(load_agent_config(agent_name), ctx=ctx)
            push({"type": "start", "run_id": run_id, "model": agent.model_spec.slug, "tools": agent.tool_names})
            cfg = {"run_id": run_id, "run_name": "playground-chat", "tags": ["playground"],
                   "metadata": {"source": "playground", "agent": agent_name, "profile": profile,
                                "variant": agent_name},
                   "recursion_limit": agent.config.recursion_limit}
            final: list = []
            for chunk in agent.graph.stream({"messages": req.messages}, config=cfg, stream_mode="values"):
                final = chunk["messages"]
                last = final[-1]
                if getattr(last, "type", "") == "ai":
                    push({"type": "model", "content": _text(last.content),
                          "tool_calls": [{"name": t["name"], "args": t["args"]} for t in (last.tool_calls or [])]})
            t = build_transcript(final, ctx, model_slug=agent.model_spec.slug, latency_s=0.0)
            push({"type": "done", "run_id": run_id, "answer": t.final_answer, "skills_loaded": t.skills_loaded,
                  "tool_calls": [c.name for c in t.tool_calls], "usage": t.usage.model_dump()})
        except Exception as e:  # noqa: BLE001
            push({"type": "error", "message": f"{type(e).__name__}: {e}"})
        finally:
            push({"type": "end"})

    task = asyncio.create_task(asyncio.to_thread(work))

    async def gen():
        try:
            while True:
                e = await queue.get()
                yield {"event": e["type"], "data": json.dumps(e, default=str)}
                if e["type"] == "end":
                    break
        finally:
            await task

    return EventSourceResponse(gen())


class FeedbackRequest(BaseModel):
    run_id: str
    thumbs: int  # 1 / 0
    comment: str = ""


@safe
def _ls_feedback(run_id: str, thumbs: int, comment: str) -> None:
    get_client().create_feedback(run_id, key="thumbs", score=float(thumbs), comment=comment)


@router.post("/chat/feedback")
def feedback(req: FeedbackRequest) -> dict:
    """Thumbs on a playground answer -> LangSmith feedback (stand-in for user feedback on traffic)."""
    d = get_settings().data_dir
    d.mkdir(parents=True, exist_ok=True)
    with (d / "feedback.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(req.model_dump()) + "\n")
    _ls_feedback(req.run_id, req.thumbs, req.comment)
    return {"ok": True}

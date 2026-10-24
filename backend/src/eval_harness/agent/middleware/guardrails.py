"""Policy checks at the trust boundaries: user input, tool arguments.

Guardrails are bound to the tool interface (not only the prompt). Every trigger is recorded as a
tripwire event on the RunContext so safety graders can assert on it.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import HumanMessage, ToolMessage

from eval_harness.agent.middleware.registry import middleware_registry
from eval_harness.agent.run_context import RunContext

INJECTION = re.compile(
    r"ignore (all |any )?(previous|prior|above) (instructions|prompts)|disregard (the )?system prompt|"
    r"reveal (your )?(system )?prompt|you are now (dan|in developer mode)", re.I)
PRIVATE_HOST = re.compile(r"^(localhost|127\.|10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.|169\.254\.|0\.0\.0\.0|\[?::1)")


class Guardrails(AgentMiddleware):
    def __init__(self, ctx: RunContext, blocked_tools: list[str] | None = None, block_injection: bool = False):
        super().__init__()
        self.ctx = ctx
        self.blocked_tools = set(blocked_tools or [])
        self.block_injection = block_injection

    @property
    def name(self) -> str:
        return "guardrails"

    def _trip(self, kind: str, detail: str) -> None:
        ev = {"kind": kind, "detail": detail}
        self.ctx.guardrail_events.append(ev)
        self.ctx.emit("guardrail", **ev)

    def before_agent(self, state, runtime):
        msgs = state.get("messages", [])
        last = next((m for m in reversed(msgs) if isinstance(m, HumanMessage)), None)
        if last and INJECTION.search(str(last.content)):
            self._trip("prompt_injection_suspected", str(last.content)[:120])
        return None

    def wrap_tool_call(self, request, handler):
        call = request.tool_call
        if call["name"] in self.blocked_tools:
            self._trip("tool_blocked", call["name"])
            return ToolMessage(content=f"BLOCKED by policy: tool '{call['name']}' is not allowed.",
                               tool_call_id=call["id"], name=call["name"], status="error")
        if call["name"] == "fetch_url":
            host = urlparse(str(call["args"].get("url", ""))).hostname or ""
            if PRIVATE_HOST.match(host):
                self._trip("ssrf_blocked", host)
                return ToolMessage(content="BLOCKED by policy: private/local addresses are not allowed.",
                                   tool_call_id=call["id"], name=call["name"], status="error")
        return handler(request)


@middleware_registry.register("guardrails")
def build(ctx: RunContext, blocked_tools: list[str] | None = None, block_injection: bool = False) -> Guardrails:
    return Guardrails(ctx, blocked_tools, block_injection)


@middleware_registry.register("tool_call_limit")
def build_tool_limit(ctx: RunContext, run_limit: int = 15, exit_behavior: str = "continue"):
    from langchain.agents.middleware import ToolCallLimitMiddleware

    return ToolCallLimitMiddleware(run_limit=run_limit, exit_behavior=exit_behavior)


@middleware_registry.register("model_call_limit")
def build_model_limit(ctx: RunContext, run_limit: int = 25, exit_behavior: str = "end"):
    from langchain.agents.middleware import ModelCallLimitMiddleware

    return ModelCallLimitMiddleware(run_limit=run_limit, exit_behavior=exit_behavior)

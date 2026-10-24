"""Inject tool failures from a YAML profile (robustness / error-recovery evals).

Profiles live in ``evals/faults/<name>.yaml``::

    rules:
      - tool: knowledge_base_search     # tool name or "*"
        mode: error | empty | timeout   # what the tool returns
        message: "503 Service Unavailable"
        first_n: 1                      # only the first N calls (omit = every call)
"""

from __future__ import annotations

from collections import Counter

import yaml
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import ToolMessage

from eval_harness.agent.middleware.registry import middleware_registry
from eval_harness.agent.run_context import RunContext
from eval_harness.core.settings import get_settings

EMPTY_TEXT = "No relevant passages found."


def load_profile(name: str) -> list[dict]:
    p = get_settings().evals_dir / "faults" / f"{name}.yaml"
    if not p.exists():
        raise FileNotFoundError(f"fault profile '{name}' not found at {p}")
    return (yaml.safe_load(p.read_text(encoding="utf-8")) or {}).get("rules", [])


class FaultInjection(AgentMiddleware):
    def __init__(self, ctx: RunContext):
        super().__init__()
        self.ctx = ctx
        self.rules = load_profile(ctx.fault_profile) if ctx.fault_profile else []
        self.counts: Counter[str] = Counter()

    @property
    def name(self) -> str:
        return "fault_injection"

    def wrap_tool_call(self, request, handler):
        call = request.tool_call
        for rule in self.rules:
            if rule.get("tool") not in (call["name"], "*"):
                continue
            self.counts[call["name"]] += 1
            first_n = rule.get("first_n")
            if first_n is not None and self.counts[call["name"]] > first_n:
                continue
            mode = rule.get("mode", "error")
            text = {"empty": EMPTY_TEXT,
                    "timeout": "ERROR: tool timed out after 30s",
                    "error": f"ERROR: {rule.get('message', 'tool unavailable')}"}[mode]
            self.ctx.note(call["id"], fault=f"{mode}:{call['name']}")
            return ToolMessage(content=text, tool_call_id=call["id"], name=call["name"],
                               status="error" if mode != "empty" else "success")
        return handler(request)


@middleware_registry.register("fault_injection")
def build(ctx: RunContext) -> FaultInjection:
    return FaultInjection(ctx)

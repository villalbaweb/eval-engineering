"""Tracks which skills the agent loaded (the signal the skill-selection graders use)."""

from __future__ import annotations

from langchain.agents.middleware import AgentMiddleware

from eval_harness.agent.middleware.registry import middleware_registry
from eval_harness.agent.run_context import RunContext
from eval_harness.skills.tools import skill_for_call


class SkillTracking(AgentMiddleware):
    def __init__(self, ctx: RunContext):
        super().__init__()
        self.ctx = ctx

    @property
    def name(self) -> str:
        return "skill_tracking"

    def wrap_tool_call(self, request, handler):
        call = request.tool_call
        result = handler(request)
        skill = skill_for_call(call["name"], call["args"], self.ctx.skills)
        ok = getattr(result, "status", None) != "error" and not str(getattr(result, "content", "")).startswith("ERROR")
        if skill and ok:
            if skill not in self.ctx.skills_loaded:
                self.ctx.skills_loaded.append(skill)
            self.ctx.emit("skill_loaded", skill=skill)
        return result


@middleware_registry.register("skill_tracking")
def build(ctx: RunContext) -> SkillTracking:
    return SkillTracking(ctx)

"""build_agent: AgentConfig -> a ``create_agent`` graph plus its RunContext.

This is the single place where the harness assembles model + tools + skills + middleware.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jinja2 import Template
from langchain.agents import create_agent
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage

from eval_harness.agent.config import AgentConfig, MiddlewareRef
from eval_harness.agent.middleware.registry import build_middleware
from eval_harness.agent.run_context import RunContext
from eval_harness.agent.transcript_builder import build_transcript
from eval_harness.evals.domain.transcript import Transcript
from eval_harness.llm.factory import make_chat_model
from eval_harness.llm.settings import ModelSpec, resolve_role
from eval_harness.skills.catalog import render_catalog
from eval_harness.skills.loader import SkillSpec, select_skills
from eval_harness.skills.tools import build_skill_tools
from eval_harness.tools.base import resolve_tools

PROMPTS_DIR = Path(__file__).parent / "prompts"

# Always-present harness middleware, outermost first / innermost last.
OUTER = ["transcript_capture", "skill_tracking"]
INNER = ["fault_injection", "tool_replay"]


def render_prompt(cfg: AgentConfig, skills: list[SkillSpec]) -> str:
    template = cfg.prompt_text or (PROMPTS_DIR / cfg.prompt).read_text(encoding="utf-8")
    return Template(template).render(skill_catalog=render_catalog(skills) if skills else "", loader_mode=cfg.skill_loader_mode)


@dataclass
class HarnessAgent:
    graph: Any
    ctx: RunContext
    config: AgentConfig
    model_spec: ModelSpec
    skills: list[SkillSpec]
    tool_names: list[str]
    system_prompt: str

    def invoke(self, messages: list[dict[str, Any]] | list[BaseMessage], *, latency_s: float | None = None,
               config: dict | None = None) -> tuple[list[BaseMessage], float]:
        import time

        t0 = time.perf_counter()
        cfg = {"recursion_limit": self.config.recursion_limit, **(config or {})}
        out = self.graph.invoke({"messages": messages}, config=cfg)
        return out["messages"], time.perf_counter() - t0

    def run(self, messages: list[dict[str, Any]], *, config: dict | None = None) -> Transcript:
        msgs, latency = self.invoke(messages, config=config)
        return build_transcript(msgs, self.ctx, model_slug=self.model_spec.slug, latency_s=latency)


def build_agent(cfg: AgentConfig, *, ctx: RunContext | None = None, model: BaseChatModel | None = None) -> HarnessAgent:
    ctx = ctx or RunContext()
    spec = resolve_role("agent", provider=cfg.model.provider, model=cfg.model.name,
                        temperature=cfg.model.temperature)
    llm = model or make_chat_model(spec=spec)

    skills = [] if cfg.skills == "none" else select_skills(cfg.skills)
    ctx.skills = skills
    tools = resolve_tools(cfg.tools)
    if skills:
        tools += build_skill_tools(skills, cfg.skill_loader_mode)

    configured = cfg.middleware_refs()
    names = {m.name for m in configured}
    refs = ([MiddlewareRef(name=n) for n in OUTER if n not in names] + configured
            + [MiddlewareRef(name=n) for n in INNER if n not in names])
    prompt = render_prompt(cfg, skills)

    graph = create_agent(model=llm, tools=tools, system_prompt=prompt,
                         middleware=build_middleware(refs, ctx), name=cfg.name)
    return HarnessAgent(graph, ctx, cfg, spec, skills, [t.name for t in tools], prompt)

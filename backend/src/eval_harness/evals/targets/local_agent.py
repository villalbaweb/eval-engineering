from __future__ import annotations

import asyncio
import hashlib
import uuid
from typing import Any

from langgraph.errors import GraphRecursionError

from eval_harness.agent.config import AgentConfig, load_agent_config
from eval_harness.agent.factory import build_agent
from eval_harness.agent.run_context import RunContext
from eval_harness.agent.transcript_builder import build_transcript
from eval_harness.evals.domain.outcome import Outcome
from eval_harness.evals.domain.suite import RunSettings, Suite
from eval_harness.evals.domain.task import Task
from eval_harness.evals.domain.transcript import Transcript
from eval_harness.evals.targets.base import Target, TrialInfo, register_target
from eval_harness.llm.settings import resolve_role
from eval_harness.tools.base import TOOL_SPECS, tool_registry


def lc_config(info: TrialInfo, task: Task, run_id: str) -> dict[str, Any]:
    """LangChain/LangSmith run config: every trial is traceable and filterable by metadata."""
    return {
        "run_id": run_id,
        "run_name": f"{info.suite}:{task.id}#{info.index}",
        "tags": ["eval-trial", f"suite:{info.suite}", *task.tags],
        "metadata": {"source": "experiment", "experiment_id": info.experiment_id, "task_id": task.id,
                     "trial_index": info.index, "trial_id": info.trial_id, **info.metadata},
    }


@register_target("local_agent")
class LocalAgentTarget(Target):
    """In-process ``create_agent`` built from an AgentConfig (the default system under test)."""

    capabilities = frozenset({"chat", "rerun", "fault_injection", "record_replay", "model_override", "traffic_sim"})

    def __init__(self, cfg: AgentConfig, *, suite_name: str = "default"):
        self.cfg = cfg
        self.suite_name = suite_name

    @classmethod
    def create(cls, suite: Suite, *, agent: str | None = None, config: AgentConfig | None = None, **_: Any):
        return cls(config or load_agent_config(agent or suite.agent), suite_name=suite.name)

    def snapshot(self) -> dict[str, Any]:
        from eval_harness.agent.factory import render_prompt
        from eval_harness.skills.loader import select_skills

        skills = [] if self.cfg.skills == "none" else select_skills(self.cfg.skills)
        spec = resolve_role("agent", provider=self.cfg.model.provider, model=self.cfg.model.name,
                            temperature=self.cfg.model.temperature)
        prompt = render_prompt(self.cfg, skills)
        tool_registry.discover()
        return {
            "type": self.type,
            "agent_config": self.cfg.model_dump(mode="json"),
            "model": spec.model_dump(),
            "prompt_sha": hashlib.sha256(prompt.encode()).hexdigest()[:12],
            "tools": sorted(tool_registry.names() if self.cfg.tools == "all" else self.cfg.tools),
            "tool_specs": {n: TOOL_SPECS[n].__dict__ for n in TOOL_SPECS},
            "skills": {s.name: {"version": s.version, "tokens": s.tokens} for s in skills},
            "skill_loader_mode": self.cfg.skill_loader_mode,
        }

    def make_ctx(self, task: Task, run: RunSettings) -> RunContext:
        return RunContext(tool_mode=run.tool_mode, cassette=task.setup.cassette or self.suite_name,
                          fault_profile=task.setup.fault_profile)

    def _invoke(self, task: Task, run: RunSettings, info: TrialInfo) -> Transcript:
        ctx = self.make_ctx(task, run)
        agent = build_agent(self.cfg, ctx=ctx)
        run_id = str(uuid.uuid4())
        msgs, latency = agent.invoke(task.input["messages"], config=lc_config(info, task, run_id))
        t = build_transcript(msgs, ctx, model_slug=agent.model_spec.slug, latency_s=latency,
                             extra_meta={"langsmith_run_id": run_id})
        return t

    async def run(self, task: Task, run: RunSettings, info: TrialInfo) -> tuple[Transcript, Outcome]:
        try:
            t = await asyncio.wait_for(asyncio.to_thread(self._invoke, task, run, info), timeout=run.timeout_s)
            return t, Outcome(final_answer=t.final_answer, status="ok")
        except TimeoutError:
            return Transcript(), Outcome(status="timeout", error=f"timed out after {run.timeout_s}s")
        except GraphRecursionError as e:
            return Transcript(), Outcome(status="step_limit", error=str(e))
        except Exception as e:  # noqa: BLE001
            return Transcript(), Outcome(status="error", error=f"{type(e).__name__}: {e}")

"""Multi-turn evaluation: a simulated user talks to the agent for several turns.

Follow-ups come from ``task.metadata['follow_ups']`` (deterministic, scripted) or, when absent,
from an LLM that plays ``task.setup.persona`` (simulator model role).
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from eval_harness.agent.config import AgentConfig, load_agent_config
from eval_harness.agent.factory import build_agent
from eval_harness.agent.transcript_builder import build_transcript
from eval_harness.evals.domain.outcome import Outcome
from eval_harness.evals.domain.suite import RunSettings, Suite
from eval_harness.evals.domain.task import Task
from eval_harness.evals.domain.transcript import Transcript
from eval_harness.evals.targets.base import TrialInfo, register_target
from eval_harness.evals.targets.local_agent import LocalAgentTarget, lc_config
from eval_harness.llm.factory import make_chat_model

SIM_SYSTEM = (
    "You are role-playing a USER talking to an evaluation-engineering assistant.\n"
    "Persona: {persona}\n"
    "Write only the user's next message (one or two sentences), reacting to the assistant's last reply. "
    "If your goal is satisfied or the conversation is going nowhere, reply exactly: DONE"
)


@register_target("multiturn_sim")
class MultiTurnSimTarget(LocalAgentTarget):
    def __init__(self, cfg: AgentConfig, *, suite_name: str = "default", max_turns: int = 3):
        super().__init__(cfg, suite_name=suite_name)
        self.max_turns = max_turns

    @classmethod
    def create(cls, suite: Suite, *, agent: str | None = None, max_turns: int = 3, **_: Any):
        return cls(load_agent_config(agent or suite.agent), suite_name=suite.name, max_turns=max_turns)

    def snapshot(self) -> dict[str, Any]:
        return {**super().snapshot(), "type": self.type, "max_turns": self.max_turns}

    def _next_user_message(self, task: Task, turn: int, messages: list[dict]) -> str | None:
        follow_ups: list[str] = task.metadata.get("follow_ups", [])
        if follow_ups:
            return follow_ups[turn] if turn < len(follow_ups) else None
        persona = task.setup.persona or "a curious engineer learning evaluation engineering"
        sim = make_chat_model("simulator")
        convo = "\n".join(f"{m['role'].upper()}: {m.get('content') or ''}" for m in messages
                          if m["role"] in ("user", "assistant") and m.get("content"))
        out = sim.invoke([("system", SIM_SYSTEM.format(persona=persona)), ("human", convo)])
        text = str(out.content).strip()
        return None if text.upper().startswith("DONE") or not text else text

    def _invoke_multi(self, task: Task, run: RunSettings, info: TrialInfo) -> Transcript:
        ctx = self.make_ctx(task, run)
        agent = build_agent(self.cfg, ctx=ctx)
        run_id = str(uuid.uuid4())
        messages: list[Any] = list(task.input["messages"])
        total_latency, lc_msgs = 0.0, None
        turns = task.setup.max_turns or self.max_turns
        for turn in range(turns):
            lc_msgs, lat = agent.invoke(messages, config=lc_config(info, task, run_id))
            total_latency += lat
            if turn == turns - 1:
                break
            from langchain_core.messages.utils import convert_to_openai_messages
            oa = convert_to_openai_messages(lc_msgs)
            nxt = self._next_user_message(task, turn, oa if isinstance(oa, list) else [oa])
            if not nxt:
                break
            messages = list(lc_msgs) + [{"role": "user", "content": nxt}]
        return build_transcript(lc_msgs or [], ctx, model_slug=agent.model_spec.slug, latency_s=total_latency,
                                extra_meta={"langsmith_run_id": run_id, "multi_turn": True})

    async def run(self, task: Task, run: RunSettings, info: TrialInfo) -> tuple[Transcript, Outcome]:
        try:
            t = await asyncio.wait_for(asyncio.to_thread(self._invoke_multi, task, run, info),
                                       timeout=run.timeout_s * self.max_turns)
            return t, Outcome(final_answer=t.final_answer, status="ok")
        except TimeoutError:
            return Transcript(), Outcome(status="timeout", error="multi-turn run timed out")
        except Exception as e:  # noqa: BLE001
            return Transcript(), Outcome(status="error", error=f"{type(e).__name__}: {e}")

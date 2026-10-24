"""Deterministic offline model ("scripted").

Used for tests, CI and key-less demos. It behaves like a plausible tool-using agent:
it loads a skill whose name overlaps the user's request, calls a general tool when
keywords match, then writes a short answer from the tool results. As a *judge*
(``with_structured_output``) it returns a trivial verdict. It exists to exercise
the plumbing, not to measure anything - real conclusions need a real model.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Sequence
from typing import Any

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import RunnableLambda

from eval_harness.llm.settings import ModelSpec

STOP = {"the", "and", "for", "with", "that", "this", "from", "your", "how", "what", "write", "make",
        "use", "load", "skill", "help", "need", "can", "you", "tool", "about", "into", "when", "will"}

OFF_TOPIC = ("ignore all previous instructions", "reveal your system prompt", "poem", "joke")

TOOL_TRIGGERS: dict[str, tuple[str, ...]] = {
    "knowledge_base_search": ("knowledge base", "kb", "corpus", "documentation", "docs say", "according to"),
    "web_search": ("web", "internet", "latest", "news", "online"),
    "current_datetime": ("current time", "what time", "today's date", "what date"),
    "stats_calculator": ("pass@k", "pass^k", "confidence interval", "cohen", "kappa", "bootstrap"),
    "trace_lookup": ("trace", "transcript of trial"),
    "results_query": ("pass rate", "experiment result", "results for"),
}


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z][a-z0-9]{3,}", text.lower()) if t not in STOP}


class ScriptedChatModel(BaseChatModel):
    tool_names: list[str] = []
    catalog: dict[str, str] = {}   # skill name -> description (parsed from system prompt)
    fail_marker: str = "[[fail]]"

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> ScriptedChatModel:
        names = []
        for t in tools:
            names.append(t["name"] if isinstance(t, dict) and "name" in t else getattr(t, "name", str(t)))
        return self.model_copy(update={"tool_names": names})

    # --- structured output (judges / synthesizers) ---
    def with_structured_output(self, schema: Any, **kwargs: Any):
        def _judge(messages: Any) -> Any:
            text = str(messages)
            ok = self.fail_marker not in text
            props = (schema.get("properties", {}) if isinstance(schema, dict) else {}) or {}
            out: dict[str, Any] = {}
            for key, spec in props.items():
                if key == "reasoning" or key == "comment":
                    out[key] = "scripted judge verdict"
                elif spec.get("type") == "boolean" or key == "score":
                    out[key] = ok if spec.get("type") != "number" else (1.0 if ok else 0.0)
                elif spec.get("type") == "array":
                    out[key] = []
                elif spec.get("type") in ("number", "integer"):
                    out[key] = 1 if ok else 0
                else:
                    out[key] = "ok"
            if not props:
                out = {"score": ok, "reasoning": "scripted judge verdict"}
            if hasattr(schema, "model_validate"):
                return schema.model_validate(out)
            return out

        return RunnableLambda(_judge)

    def _generate(self, messages: list[BaseMessage], stop: list[str] | None = None,
                  run_manager: CallbackManagerForLLMRun | None = None, **kwargs: Any) -> ChatResult:
        return ChatResult(generations=[ChatGeneration(message=self._respond(messages))])

    # ------------------------------------------------------------------
    def _respond(self, messages: list[BaseMessage]) -> AIMessage:
        system = next((m.content for m in messages if isinstance(m, SystemMessage)), "")
        last_human_idx = max((i for i, m in enumerate(messages) if isinstance(m, HumanMessage)), default=-1)
        human = str(messages[last_human_idx].content) if last_human_idx >= 0 else ""
        since = messages[last_human_idx + 1:]
        tool_msgs = [m for m in since if isinstance(m, ToolMessage)]
        called = {tc["name"] for m in since if isinstance(m, AIMessage) for tc in (m.tool_calls or [])}
        called_args = {(tc["name"], str(tc["args"])) for m in since if isinstance(m, AIMessage) for tc in (m.tool_calls or [])}

        if self.fail_marker in human or any(k in human.lower() for k in OFF_TOPIC):
            return AIMessage(content="I can only help with evaluation engineering, so I can't help with that.")

        calls: list[dict[str, Any]] = []
        want = _tokens(human)
        low = human.lower()

        # 1) skill loading
        for name in self.tool_names:
            if name.startswith("load_skill_") and name not in called:
                skill_tokens = _tokens(name[len("load_skill_"):].replace("_", " "))
                if skill_tokens & want or any(s[:5] in low for s in skill_tokens if len(s) > 5):
                    calls.append({"name": name, "args": {}})
        if "load_skill" in self.tool_names and "load_skill" not in called:
            for line in re.findall(r"^- ([\w\-]+): (.+)$", system, flags=re.M):
                skill, desc = line
                tokens = _tokens(skill.replace("-", " "))
                if tokens & want or any(t[:5] in low for t in tokens if len(t) > 5):
                    calls.append({"name": "load_skill", "args": {"name": skill}})
                    break

        # 2) general tools
        for tool, triggers in TOOL_TRIGGERS.items():
            if tool in self.tool_names and tool not in called and any(t in low for t in triggers):
                calls.append({"name": tool, "args": self._args_for(tool, human)})

        calls = [c for c in calls if (c["name"], str(c["args"])) not in called_args]
        if calls and len(tool_msgs) < 6:
            return AIMessage(
                content="",
                tool_calls=[{"id": f"call_{uuid.uuid4().hex[:8]}", "name": c["name"], "args": c["args"], "type": "tool_call"}
                            for c in calls],
            )

        if tool_msgs:
            snippets = " | ".join(str(m.content).strip().replace("\n", " ")[:160] for m in tool_msgs[-3:])
            return AIMessage(content=f"Based on what I found: {snippets}")
        return AIMessage(content=f"Here is a direct answer to: {human[:200]}")

    @staticmethod
    def _args_for(tool: str, human: str) -> dict[str, Any]:
        if tool in ("knowledge_base_search", "web_search"):
            return {"query": human[:200]}
        if tool == "stats_calculator":
            return {"operation": "pass_at_k", "n": 10, "c": 6, "k": 3}
        if tool == "current_datetime":
            return {}
        if tool == "trace_lookup":
            return {"trial_id": "latest"}
        if tool == "results_query":
            return {"experiment_id": "latest"}
        return {}


def _catalog_from(spec: ModelSpec) -> ScriptedChatModel:
    return ScriptedChatModel()


def build(spec: ModelSpec) -> ScriptedChatModel:
    return _catalog_from(spec)

"""Record / replay tool outputs for deterministic runs.

record: call the real tool and store its output in the cassette.
replay: serve outputs from the cassette; a miss returns an explicit error so it is visible.
Only tools marked ``replayable`` participate (e.g. not ``current_datetime``).
"""

from __future__ import annotations

import json
from pathlib import Path

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import ToolMessage

from eval_harness.agent.middleware.registry import middleware_registry
from eval_harness.agent.run_context import RunContext
from eval_harness.core.settings import get_settings
from eval_harness.tools.base import tool_spec


def cassette_path(name: str) -> Path:
    return get_settings().cassettes_dir / f"{name}.json"


def call_key(tool: str, args: dict) -> str:
    return f"{tool}:{json.dumps(args, sort_keys=True, default=str)}"


class ToolReplay(AgentMiddleware):
    def __init__(self, ctx: RunContext):
        super().__init__()
        self.ctx = ctx
        self._data: dict[str, str] | None = None

    @property
    def name(self) -> str:
        return "tool_replay"

    def _load(self) -> dict[str, str]:
        if self._data is None:
            p = cassette_path(self.ctx.cassette or "default")
            self._data = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
        return self._data

    def _save(self) -> None:
        p = cassette_path(self.ctx.cassette or "default")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self._data, indent=2, sort_keys=True), encoding="utf-8")

    def wrap_tool_call(self, request, handler):
        mode = self.ctx.tool_mode
        call = request.tool_call
        spec = tool_spec(call["name"])
        if mode == "live" or (spec is not None and not spec.replayable):
            return handler(request)
        key = call_key(call["name"], call["args"])
        if mode == "replay":
            data = self._load()
            if key in data:
                self.ctx.note(call["id"], replayed=True)
                return ToolMessage(content=data[key], tool_call_id=call["id"], name=call["name"])
            return ToolMessage(content=f"ERROR: cassette miss for {key}", tool_call_id=call["id"],
                               name=call["name"], status="error")
        result = handler(request)  # record
        content = getattr(result, "content", None)
        if isinstance(content, str) and not content.startswith("ERROR"):
            self._load()[key] = content
            self._save()
        return result


@middleware_registry.register("tool_replay")
def build(ctx: RunContext) -> ToolReplay:
    return ToolReplay(ctx)

"""In-process pub/sub for experiment progress (feeds SSE) and active-run bookkeeping."""

from __future__ import annotations

import asyncio
from typing import Any

from eval_harness.evals.runner.executor import ExperimentRunner


class EventBus:
    def __init__(self) -> None:
        self.history: dict[str, list[dict[str, Any]]] = {}
        self.subs: dict[str, set[asyncio.Queue]] = {}
        self.runners: dict[str, ExperimentRunner] = {}
        self.tasks: dict[str, asyncio.Task] = {}

    def publish(self, exp_id: str, event: dict[str, Any]) -> None:
        self.history.setdefault(exp_id, []).append(event)
        for q in self.subs.get(exp_id, ()):
            q.put_nowait(event)

    async def subscribe(self, exp_id: str):
        q: asyncio.Queue = asyncio.Queue()
        self.subs.setdefault(exp_id, set()).add(q)
        try:
            for e in list(self.history.get(exp_id, [])):  # replay for late subscribers
                yield e
                if e["type"] == "experiment_done":
                    return
            while True:
                e = await q.get()
                yield e
                if e["type"] == "experiment_done":
                    return
        finally:
            self.subs.get(exp_id, set()).discard(q)

    def launch(self, runner: ExperimentRunner) -> str:
        exp_id = runner.exp.id
        runner.on_event = lambda e, _id=exp_id: self.publish(_id, e)
        self.runners[exp_id] = runner

        async def _go() -> None:
            try:
                await runner.run()
            finally:
                self.runners.pop(exp_id, None)

        self.tasks[exp_id] = asyncio.create_task(_go())
        return exp_id


bus = EventBus()

"""Targets: the thing being evaluated.

A target turns a :class:`Task` into a ``(Transcript, Outcome)``. The engine never depends on
LangChain; to evaluate something else (another agent, an HTTP service) add one file here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar

from eval_harness.core.registry import Registry
from eval_harness.evals.domain.outcome import Outcome
from eval_harness.evals.domain.suite import RunSettings, Suite
from eval_harness.evals.domain.task import Task
from eval_harness.evals.domain.transcript import Transcript


@dataclass
class TrialInfo:
    experiment_id: str
    trial_id: str
    index: int
    suite: str
    metadata: dict[str, Any] = field(default_factory=dict)


CAPABILITIES = ("chat", "rerun", "fault_injection", "record_replay", "model_override", "traffic_sim")


class Target:
    type: ClassVar[str] = ""
    # what a variant using this target supports (the UI and the runner gate features on it):
    # chat (Playground, multiturn mode), rerun (live mode), fault_injection, record_replay (tool modes),
    # model_override, traffic_sim. None = undeclared (targets written before profiles): never gated.
    capabilities: ClassVar[frozenset[str] | None] = None

    async def run(self, task: Task, run: RunSettings, info: TrialInfo) -> tuple[Transcript, Outcome]:
        raise NotImplementedError

    def snapshot(self) -> dict[str, Any]:
        """Everything that explains this target's behaviour (stored with the experiment)."""
        return {"type": self.type}

    @classmethod
    def create(cls, suite: Suite, **options: Any) -> Target:
        return cls()


target_registry: Registry[type[Target]] = Registry(
    "target", package="eval_harness.evals.targets", entry_point_group="eval_harness.targets"
)


def target_capabilities(type_: str) -> frozenset[str] | None:
    """Capabilities of a target type; None when the target does not declare them (not gated).
    Unknown target names support nothing."""
    return target_registry.get(type_).capabilities if type_ in target_registry else frozenset()


def register_target(type_: str):
    def deco(cls: type[Target]) -> type[Target]:
        cls.type = type_
        target_registry.register(type_)(cls)
        return cls

    return deco

"""Middleware plug-in registry.

A middleware builder is ``build(ctx: RunContext, **args) -> AgentMiddleware``. Register it with
``@middleware_registry.register("name")``; agent configs refer to it by name.
Order in an agent config is outermost-first (the first entry wraps all others).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from langchain.agents.middleware import AgentMiddleware

from eval_harness.agent.run_context import RunContext
from eval_harness.core.registry import Registry

MiddlewareBuilder = Callable[..., AgentMiddleware]

middleware_registry: Registry[MiddlewareBuilder] = Registry(
    "middleware", package="eval_harness.agent.middleware", entry_point_group="eval_harness.middleware"
)


def build_middleware(refs: list[Any], ctx: RunContext) -> list[AgentMiddleware]:
    return [middleware_registry.get(r.name)(ctx, **r.args) for r in refs]

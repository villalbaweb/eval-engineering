"""Tool registry and metadata.

A tool module defines a LangChain ``@tool`` and decorates it with ``@register_tool(...)``.
The metadata (``ToolSpec``) drives record/replay (``replayable``), fault injection and the
UI catalog. Dropping a new file into ``tools/`` is enough to make it available.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from langchain_core.tools import BaseTool

from eval_harness.core.registry import Registry

tool_registry: Registry[BaseTool] = Registry(
    "tool", package="eval_harness.tools", entry_point_group="eval_harness.tools"
)


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    side_effects: bool = False  # writes to the outside world
    replayable: bool = True  # output may be recorded/replayed from a cassette
    cost_hint: str = "low"  # low | medium | high
    tags: tuple[str, ...] = field(default_factory=tuple)


TOOL_SPECS: dict[str, ToolSpec] = {}


def register_tool(*, side_effects: bool = False, replayable: bool = True, cost_hint: str = "low",
                  tags: tuple[str, ...] = ()) -> Callable[[BaseTool], BaseTool]:
    def deco(t: BaseTool) -> BaseTool:
        TOOL_SPECS[t.name] = ToolSpec(t.name, (t.description or "").split("\n")[0], side_effects,
                                      replayable, cost_hint, tags)
        tool_registry.register(t.name)(t)
        return t

    return deco


def resolve_tools(names: list[str] | str) -> list[BaseTool]:
    """``"all"`` or a list of tool names -> tool objects."""
    tool_registry.discover()
    if names == "all":
        names = tool_registry.names()
    return [tool_registry.get(n) for n in names]


def tool_spec(name: str) -> ToolSpec | None:
    tool_registry.discover()
    return TOOL_SPECS.get(name)

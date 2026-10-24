"""Tier 2/3 of progressive disclosure: tools that load a skill (or one of its assets) on demand.

Two loader modes are an experiment in themselves:
  per_skill - one ``load_skill_<name>`` tool per skill (tool list grows with the library)
  generic   - a single ``load_skill(name)`` tool (constant tool list; relies on the catalog)
"""

from __future__ import annotations

from typing import Literal

from langchain_core.tools import BaseTool, StructuredTool, tool

from eval_harness.skills.loader import SkillSpec

LoaderMode = Literal["per_skill", "generic"]


def _per_skill_tool(spec: SkillSpec) -> BaseTool:
    def _load() -> str:
        return spec.body

    return StructuredTool.from_function(
        func=_load,
        name=spec.tool_name,
        description=f"Load the '{spec.name}' skill instructions. {spec.description} "
                    "Call this before doing the task it covers.",
    )


def build_skill_tools(skills: list[SkillSpec], mode: LoaderMode = "per_skill") -> list[BaseTool]:
    by_name = {s.name: s for s in skills}
    tools: list[BaseTool] = []
    if mode == "per_skill":
        tools.extend(_per_skill_tool(s) for s in skills)
    else:
        @tool
        def load_skill(name: str) -> str:
            """Load the full instructions of a skill by name. Choose from the skill catalog in the
            system prompt. Call this before doing the task the skill covers."""
            s = by_name.get(name)
            if s is None:
                return f"ERROR: unknown skill '{name}'. Available skills: {', '.join(sorted(by_name))}"
            return s.body

        tools.append(load_skill)

    if any(s.assets for s in skills):
        @tool
        def read_skill_asset(skill: str, path: str) -> str:
            """Read an extra file bundled with a skill (templates, examples). The skill body lists
            the available asset paths. Only read assets you actually need."""
            from pathlib import Path

            s = by_name.get(skill)
            if s is None:
                return f"ERROR: unknown skill '{skill}'."
            if path not in s.assets:
                return f"ERROR: '{path}' is not an asset of '{skill}'. Available: {s.assets}"
            return (Path(s.path) / path).read_text(encoding="utf-8")

        tools.append(read_skill_asset)
    return tools


def skill_for_call(tool_name: str, args: dict, skills: list[SkillSpec]) -> str | None:
    """Which skill (if any) does this tool call load? Used by the skill_tracking middleware."""
    if tool_name == "load_skill":
        name = args.get("name")
        return name if any(s.name == name for s in skills) else None
    for s in skills:
        if s.tool_name == tool_name:
            return s.name
    return None

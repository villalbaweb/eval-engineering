"""The agent's tools and skills (metadata; never executed) and checks of expectations against them."""

from __future__ import annotations

from typing import Any

from eval_harness.evals.domain.profile import Profile
from eval_harness.evals.domain.task import Task


def inventory(p: Profile) -> dict[str, Any]:
    """Tools and skills of the agent. The built-in copilot is introspected from the lab's registries."""
    if not p.inventory.from_registry:
        return {"tools": [t.model_dump() for t in p.inventory.tools],
                "skills": [s.model_dump() for s in p.inventory.skills], "from_registry": False}
    from eval_harness.skills.loader import load_library
    from eval_harness.tools.base import TOOL_SPECS, tool_registry

    tool_registry.discover()
    lib = load_library()
    tools = [{"name": n, "description": (tool_registry.get(n).description or "").strip().split("\n")[0],
              "side_effects": bool(getattr(s, "side_effects", False))} for n, s in sorted(TOOL_SPECS.items())]
    # each skill's loader tool is a tool the agent can call too
    tools += [{"name": k.tool_name, "description": f"loads skill {k.name}", "side_effects": False} for k in lib.values()]
    return {"tools": tools, "skills": [{"name": k.name, "description": k.description, "side_effects": False}
                                       for k in lib.values()], "from_registry": True}


def expectation_warnings(tasks: list[Task], p: Profile) -> list[str]:
    """Expectations naming tools/skills this agent does not have (likely typos or a stale inventory).
    Warnings only: an inventory can lag behind the agent. Empty inventory = nothing to check."""
    inv = inventory(p)
    tools = {t["name"] for t in inv["tools"]} | ({"load_skill"} if inv["from_registry"] else set())
    skills = {s["name"] for s in inv["skills"]}
    out = []
    for t in tasks:
        e = t.expected
        if tools:
            names = [c.name for c in e.tool_calls] + list(e.forbidden_tools)
            out += [f"{t.id}: tool '{n}' is not in the '{p.name}' inventory" for n in names if n not in tools]
        if skills:
            names = list(e.skills_loaded) + list(e.forbidden_skills)
            out += [f"{t.id}: skill '{n}' is not in the '{p.name}' inventory" for n in names if n not in skills]
    return out

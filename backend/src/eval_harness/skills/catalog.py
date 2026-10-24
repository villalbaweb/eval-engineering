"""Tier 1 of progressive disclosure: the lightweight catalog placed in the system prompt."""

from __future__ import annotations

from eval_harness.skills.loader import SkillSpec


def render_catalog(skills: list[SkillSpec]) -> str:
    if not skills:
        return "(no skills available)"
    return "\n".join(f"- {s.name}: {s.description}" for s in skills)

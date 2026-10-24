from __future__ import annotations

from eval_harness.evals.data_sources.synthesis import llm
from eval_harness.evals.data_sources.synthesis.base import Generator, register_generator
from eval_harness.evals.domain.task import Task
from eval_harness.skills.loader import load_library


@register_generator("skill_targeted")
class SkillTargeted(Generator):
    """For every skill: queries that SHOULD load it (positive) and near-misses that should NOT
    (negative, expected.forbidden_skills). Built from each skill's own description so the dataset
    grows automatically when a skill is added to the library."""

    description = "Positive and near-miss queries per skill, derived from the skill library."

    def generate(self) -> list[Task]:
        skills = load_library()
        names = self.cfg.options.get("skills") or list(skills)
        per_skill = max(1, self.cfg.count // max(1, len(names) * 2))
        out, i = [], 0
        for name in names:
            s = skills[name]
            for j in range(per_skill):
                pos = llm.write(
                    f"Skill: {s.name} - {s.description}\nWrite ONE realistic user message that clearly needs "
                    f"this skill, without mentioning the skill name. Variation #{j + 1}.",
                    lambda s=s, j=j: f"I need help with this: {s.description.rstrip('.').lower()} (case {j + 1})")
                out.append(self.make_task(i, pos, {"skills_loaded": [name]}, extra_tags=["skill-selection", name, "positive"],
                                          metadata={"skill": name, "polarity": "positive"}))
                i += 1
                neg = llm.write(
                    f"Skill: {s.name} - {s.description}\nWrite ONE realistic user message about a SIMILAR but "
                    f"different topic that does NOT need this skill. Variation #{j + 1}.",
                    lambda s=s, j=j, n=name: f"Give me a one-line definition of a term related to {n.split('-')[0]} (case {j + 1}).")
                out.append(self.make_task(i, neg, {"forbidden_skills": [name]},
                                          extra_tags=["skill-selection", name, "negative"],
                                          metadata={"skill": name, "polarity": "negative"}))
                i += 1
        return out[: self.cfg.count] if self.cfg.count < len(out) else out

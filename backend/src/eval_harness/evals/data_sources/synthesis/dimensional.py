from __future__ import annotations

import itertools
from typing import Any

from eval_harness.evals.data_sources.synthesis import llm
from eval_harness.evals.data_sources.synthesis.base import (
    Generator,
    merge_expected,
    register_generator,
)
from eval_harness.evals.domain.task import Task


def _values(dim: Any) -> list[tuple[str, dict[str, Any]]]:
    """A dimension is a list of values, or a mapping value -> expected-fragment."""
    if isinstance(dim, dict):
        return [(str(k), v or {}) for k, v in dim.items()]
    return [(str(v), {}) for v in dim]


@register_generator("dimensional")
class Dimensional(Generator):
    """Dimensions -> sampled tuples -> one realistic query per tuple (avoids the repetitive
    'give me 50 questions' failure mode). Tuples are shuffled across the full cartesian product so
    rare combinations are covered before any combination repeats."""

    description = "Sample tuples of dimension values and turn each into a realistic user message."

    def generate(self) -> list[Task]:
        dims = {name: _values(spec) for name, spec in self.cfg.dimensions.items()}
        names = list(dims)
        combos = list(itertools.product(*[dims[n] for n in names]))
        self.rng.shuffle(combos)
        tasks = []
        for i in range(self.cfg.count):
            combo = combos[i % len(combos)]
            chosen = {n: v for n, (v, _) in zip(names, combo, strict=True)}
            expected = merge_expected([frag for _, frag in combo])
            desc = ", ".join(f"{k}={v}" for k, v in chosen.items())
            prompt = (f"Write ONE realistic message a user would send to an evaluation-engineering assistant.\n"
                      f"Attributes: {desc}.\nOutput only the message.")
            text = llm.write(prompt, lambda c=chosen: self._template(c))
            tasks.append(self.make_task(i, text, expected, metadata={"dims": chosen}))
        return tasks

    @staticmethod
    def _template(chosen: dict[str, str]) -> str:
        intent = chosen.get("intent", "evaluate my agent")
        persona = chosen.get("persona")
        diff = chosen.get("difficulty", "")
        lead = {"novice": "I am new to this: ", "expert": "", "terse": ""}.get(str(persona).split()[0].lower(), "")
        tail = " Please include concrete steps and an example." if "detail" in diff else ""
        return f"{lead}{intent[0].upper() + intent[1:]}.{tail}"

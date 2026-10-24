from __future__ import annotations

from eval_harness.evals.data_sources.synthesis import llm
from eval_harness.evals.data_sources.synthesis.base import Generator, register_generator
from eval_harness.evals.datasets.loader import load_tasks
from eval_harness.evals.domain.task import Task

TRANSFORMS = {
    "paraphrase": ("Rewrite the message with different wording but the same meaning.", lambda t: f"Could you help with this: {t}"),
    "harder": ("Rewrite the message so it needs more steps or combines two related needs.",
               lambda t: f"{t} Also explain how I would verify the result."),
    "missing_info": ("Rewrite the message as a vaguer version missing key details.", lambda t: t.split(".")[0].split("?")[0] + "?"),
    "multi_intent": ("Rewrite the message so it also contains an unrelated second request.",
                     lambda t: f"{t} Also, what time is it in UTC?"),
}


@register_generator("trace_seeded")
class TraceSeeded(Generator):
    """Variations of existing inputs. options: seed_datasets (globs; default all), transforms (list).
    'missing_info' variants drop the expected evidence because the right behaviour is no longer certain."""

    description = "Create paraphrased / harder / vaguer / multi-intent variations of existing task inputs."

    def generate(self) -> list[Task]:
        seeds = load_tasks(self.cfg.options.get("seed_datasets") or None)
        seeds = [s for s in seeds if s.source == "manual"] or seeds
        transforms = self.cfg.options.get("transforms") or list(TRANSFORMS)
        out = []
        for i in range(self.cfg.count):
            seed = seeds[self.rng.randrange(len(seeds))]
            kind = transforms[i % len(transforms)]
            instruction, fallback = TRANSFORMS[kind]
            text = llm.write(f"{instruction}\n\nMessage: {seed.user_text}\n\nOutput only the new message.",
                             lambda f=fallback, s=seed: f(s.user_text))
            exp = {} if kind == "missing_info" else seed.expected.model_dump(mode="json", exclude_defaults=True)
            if kind == "multi_intent":  # the original evidence still holds, answer text checks may not
                exp.pop("answer_contains", None)
                exp.pop("final_answer_criteria", None)
            out.append(self.make_task(i, text, exp, extra_tags=[kind, *seed.tags[:2]],
                                      metadata={"seed_task": seed.id, "transform": kind}))
        return out

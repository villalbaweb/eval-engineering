from __future__ import annotations

from eval_harness.evals.data_sources.synthesis import llm
from eval_harness.evals.data_sources.synthesis.base import Generator, register_generator
from eval_harness.evals.domain.task import Task

PERSONAS = {
    "impatient engineer": "wants short answers and pushes back if the answer is vague",
    "careful researcher": "asks for sources and checks claims",
    "confused beginner": "does not know the terminology and asks follow-up questions",
}


@register_generator("multiturn_personas")
class MultiturnPersonas(Generator):
    """Multi-turn tasks: an opening message + a persona that the simulator target plays (or scripted
    follow-ups when generated offline). Use with target 'multiturn_sim'."""

    description = "Persona-driven multi-turn conversations for the simulated-user target."

    def generate(self) -> list[Task]:
        topics = list((self.cfg.dimensions.get("topic") or {"how to read agent trajectories": {}}).keys()
                      if isinstance(self.cfg.dimensions.get("topic"), dict) else
                      self.cfg.dimensions.get("topic") or ["how to read agent trajectories"])
        personas = self.cfg.dimensions.get("persona") or list(PERSONAS)
        out = []
        for i in range(self.cfg.count):
            topic, persona = topics[i % len(topics)], personas[i % len(personas)]
            traits = PERSONAS.get(persona, "")
            opening = llm.write(f"Write the FIRST message from a {persona} ({traits}) asking about: {topic}.",
                                lambda t=topic: f"Can you help me understand {t}?")
            follow = [llm.write(f"Write a short follow-up from a {persona} after the assistant answered about {topic}.",
                                lambda: "Can you give me a concrete example, and check the knowledge base?")]
            out.append(self.make_task(i, opening, {}, extra_tags=["multi-turn"],
                                      setup={"persona": f"{persona}: {traits}", "max_turns": 3},
                                      metadata={"follow_ups": follow, "dims": {"persona": persona, "topic": topic}}))
        return out

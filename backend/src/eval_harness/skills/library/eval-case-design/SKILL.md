---
name: eval-case-design
description: Design evaluation test cases (tasks) with unambiguous inputs, success criteria, reference trajectories and capability/regression tags.
version: "1"
tags: [datasets, tasks]
---

# Designing eval cases

A **task** is one input plus everything needed to decide whether the agent handled it well.

## Checklist
1. **One behaviour per task.** If it can fail for two unrelated reasons, split it.
2. **Unambiguous success.** Two domain experts reading the task should agree on pass/fail. If not, tighten the input or the criteria.
3. **State the expected evidence**, not only the answer:
   - `skills_loaded` / `forbidden_skills` (did it pick the right skill?)
   - `tool_calls` with a `trajectory_mode` (`superset` when extra calls are harmless, `strict` only when order matters)
   - `answer_contains` / `answer_not_contains` for hard facts
   - `final_answer_criteria` for things only a judge can check
4. **Tag it** `capability` (hard, expected to fail sometimes) or `regression` (must always pass), plus a topic tag.
5. **Include negatives**: requests that should NOT trigger a skill or tool, and out-of-scope requests that should be refused.
6. **Prefer deterministic grounding**: use the local knowledge base so the right answer is known.

## Anti-patterns
- Reference answers that leak into the input.
- Tasks that depend on live web content (flaky) unless the tool is replayed from a cassette.
- Criteria like "is helpful" without an anchored definition.

## Output format
Produce YAML with: `id`, `kind`, `tags`, `input.messages`, `expected`, `graders`.

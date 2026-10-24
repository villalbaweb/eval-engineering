---
name: synthetic-data-generation
description: Generate diverse synthetic eval tasks from dimensions and tuples, add adversarial and edge cases, and avoid label leakage.
version: "1"
tags: [datasets, synthetic]
---

# Synthetic task generation

## Method: dimensions -> tuples -> queries
1. List **dimensions** that change agent behaviour, e.g. `intent` (design a rubric, analyse errors, compare experiments), `persona` (novice, expert, terse), `difficulty` (single step, multi-step), `needed_skill`.
2. **Sample tuples** of dimension values (cover rare combinations on purpose).
3. For each tuple, ask an LLM to write ONE realistic user message. Do not generate lists of questions in one call; they come out repetitive.
4. Add the expected evidence (skills, tools, facts) from the tuple, **not** from the generated text.

## Edge and adversarial cases
- near-miss requests that should NOT load a skill
- prompt-injection attempts, out-of-scope asks, ambiguous requests
- missing information that requires a clarifying question

## Quality gates
- **Deduplicate** (fuzzy match) and check diversity per dimension.
- **Leakage check**: the expected answer must not appear in the input.
- **Review a sample by hand** before accepting; reject unrealistic items.
- Tag every task `source: synthetic:<generator>` so you can later compare against real traffic.

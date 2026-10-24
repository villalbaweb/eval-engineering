---
name: rubric-authoring
description: Write LLM-as-judge rubrics - binary or anchored criteria, few-shot examples, and mitigations for judge bias.
version: "1"
tags: [graders, llm-judge]
---

# Authoring a judge rubric

## Principles
- **One criterion per judge call.** Do not ask for "quality"; ask whether a specific, observable property holds.
- **Binary first.** Pass/fail with a written definition is more reliable than a 1-10 scale. If you need a scale, anchor every level with a concrete description.
- **Ask for reasoning before the verdict**, and keep the verdict machine-readable.
- **Show the judge what it needs**: user input, final answer, and (for groundedness) the tool results. Hide what it must not use.
- **Use a different, stronger model** than the agent under test (self-preference bias).

## Bias mitigations
- Pairwise comparisons: run both orders and only accept agreement (position bias).
- Penalize padding explicitly (verbosity bias).
- Keep the rubric stable; version it. A small wording change can move scores.

## Process
1. Draft the criterion and 2 pass + 2 fail examples.
2. Run it on ~30 stored transcripts you graded by hand.
3. Compute coverage / false failure rate (see the grader-calibration skill) and revise.

A fill-in template is available as asset `templates/rubric.md`; a worked example as `examples/groundedness.md`.

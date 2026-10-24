---
name: trajectory-analysis
description: Read agent transcripts step by step to find wrong tool choice, bad arguments, loops, skipped steps and weak error recovery.
version: "1"
tags: [analysis, trajectories]
---

# Analysing a trajectory

Walk the transcript in order and answer, at every step:

1. **Plan** - did the agent identify what was needed before acting?
2. **Tool selection** - was this the right tool (or skill) for the sub-goal? Was a cheaper deterministic tool available?
3. **Arguments** - are they well-formed and complete? Did the agent invent values?
4. **Interpretation** - did it read the tool result correctly, or ignore/misquote it?
5. **Recovery** - after an error result, did it retry sensibly, adapt, or give up/hallucinate?
6. **Efficiency** - redundant calls, repeated identical calls (loops), unnecessary skill loads.
7. **Termination** - did it stop when done, and is the final answer supported by what it found?

## Signals to compute
- steps vs. the reference trajectory; identical consecutive tool calls; tool-error count
- skills loaded but never used; needed skill never loaded

## Reporting
For each failing trial write ONE sentence naming the first step where it went wrong. That sentence is the raw material for the error-analysis skill.

Remember: a correct final answer can hide a bad trajectory (e.g. it skipped a required lookup and guessed correctly).

---
name: grader-calibration
description: Validate the validators - measure coverage, false failure rate, alignment and Cohen's kappa of a grader against human labels.
version: "1"
tags: [graders, calibration]
---

# Calibrating a grader

An uncalibrated grader gives you confident numbers about the wrong thing.

## Procedure
1. Collect ~30-50 stored trials. Label each yourself as good/bad (thumbs) in the Annotate view.
2. Compare the grader's pass/fail with your labels:
   - **Coverage** = share of human-BAD trials the grader also fails (want high)
   - **False failure rate (FFR)** = share of human-GOOD trials the grader fails (want low)
   - **Alignment** = harmonic mean of coverage and (1 - FFR)
   - **Cohen's kappa** = agreement beyond chance (>0.6 is decent)
3. Inspect disagreements one by one. Decide whether the grader or your label is wrong.
4. Revise the rubric/assertion, then **re-grade the stored transcripts** (no need to re-run the agent) and recompute.

## Criteria drift
Expect your standard to move while labelling. When it does, update the written criteria and re-label a few earlier trials so the dataset stays consistent.

## Rules of thumb
- Few false failures matter more for graders on the critical path; high coverage matters more for monitoring.
- Do not tune a grader on the same trials you use to report its quality - hold some out.
- Use the `stats_calculator` tool for kappa and confidence intervals.

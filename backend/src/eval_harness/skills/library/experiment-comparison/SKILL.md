---
name: experiment-comparison
description: Compare two experiments statistically - pass@k vs pass^k, confidence intervals, significance tests, and cost/latency trade-offs.
version: "1"
tags: [analysis, statistics]
---

# Comparing experiments

1. **Same tasks, same k.** Only compare runs of the same suite version; note any config difference (model, prompt, loader mode).
2. **Report rates with intervals.** A pass rate without a confidence interval is not a result. Use the bootstrap CI (or Wilson interval) from `stats_calculator`.
3. **Choose the right metric**
   - `pass@k` - can it succeed if allowed to retry? (capability)
   - `pass^k` - does it succeed every time? (reliability)
4. **Test the difference.** Paired tasks -> McNemar on discordant pairs; independent samples -> two-proportion z-test. Small samples need large effects.
5. **Read the per-task diff**, regressions first. A flat average can hide trade-offs between task groups.
6. **Weigh cost and latency**: tokens, dollars and p95 latency per task. A 2-point gain at 5x cost may not be worth it.
7. **Decide with a rule written beforehand** (e.g. "ship if no regression on the regression suite and pass^3 improves").

Use `results_query` to read stored summaries and `stats_calculator` for exact numbers.

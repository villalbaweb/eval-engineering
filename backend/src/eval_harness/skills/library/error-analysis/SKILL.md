---
name: error-analysis
description: Turn failing transcripts into a failure taxonomy via open and axial coding, then into new graders and tasks.
version: "1"
tags: [analysis, taxonomy]
---

# Error analysis

1. **Sample** 30-100 failing or low-scored trials (mix of tasks; include user-reported failures if any).
2. **Open coding**: for each, write a short free-text note on what went wrong *first*. Do not pre-define categories.
3. **Axial coding**: cluster similar notes into 5-10 categories (e.g. "wrong skill loaded", "fabricated tool argument", "ignored tool error", "answer not grounded").
4. **Count** per category; fix the most frequent first.
5. **Close the loop** for each category:
   - add 3-5 tasks that reproduce it (tag them with the category)
   - add or tighten a grader that detects it (code grader if observable, judge otherwise)
   - re-run and confirm the category count drops
6. **Re-sample** periodically; the taxonomy drifts as the agent changes (criteria drift).

## Tips
- Read transcripts, not just scores. Aggregate metrics hide the story.
- Keep a "not a bug" bucket for task/grader defects; fixing the eval is a valid outcome.
- Use the `trace_lookup` tool to fetch transcripts and `results_query` to see where failures concentrate.

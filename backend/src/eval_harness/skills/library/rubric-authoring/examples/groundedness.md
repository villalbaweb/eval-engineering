# Example rubric: groundedness

**Question:** Is every factual claim in the answer supported by the tool results shown?

**Pass when:** each claim can be matched to a passage in the tool results, or is clearly marked as general knowledge.
**Fail when:** the answer states a specific number, name or definition that appears in no tool result.

- PASS: tool result says "pass@k = 1 - C(n-c,k)/C(n,k)"; answer repeats that formula.
- FAIL: tool result has no pass^k definition; answer invents "pass^k is the median of k trials".

You are checking whether an AI assistant answer is grounded in the tool results it was given.

Criterion: every specific factual claim (definitions, formulas, numbers, names) in the answer is supported by the tool results below, or is clearly general common knowledge.

PASS: all specific claims can be traced to the tool results.
FAIL: the answer states a specific claim that appears in none of the tool results, or contradicts them.

<tool_results>
{tool_results}
</tool_results>

<assistant_answer>
{outputs}
</assistant_answer>

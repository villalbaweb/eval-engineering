# LLM-as-a-judge

An LLM judge grades outputs against an explicit rubric and returns a score plus reasoning. Prefer binary or anchored-scale criteria over vague 1-10 scores. Use a different and stronger model than the agent under test, because models tend to favour their own outputs (self-preference bias).

Known biases: position bias in pairwise comparisons (mitigate by swapping the order and requiring agreement), verbosity bias (longer answers score higher), and sensitivity to small wording changes in the grader prompt.

Always validate a judge against human labels before trusting it.

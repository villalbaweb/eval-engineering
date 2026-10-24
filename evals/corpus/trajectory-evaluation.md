# Trajectory evaluation

Trajectory evaluation checks the path an agent took: the sequence of tool calls, their arguments and the recovery from errors, not only the final answer. It reveals problems that outcome-only grading hides, such as skipping a safety check or calling redundant tools.

The agentevals library offers four trajectory match modes: strict (same messages and tool calls in the same order), unordered (same tool calls in any order), subset (the agent calls only tools from the reference), and superset (the agent calls at least the reference tools; extras allowed).

A subsequence score gives partial credit: the fraction of expected steps that appear in order in the actual trajectory.

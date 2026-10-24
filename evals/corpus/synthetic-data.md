# Synthetic data for evals

Do not ask an LLM for fifty test questions in one prompt; the results are repetitive. Instead define dimensions (for example intent, persona, difficulty), sample tuples of dimension values, and turn each tuple into a realistic query.

Deduplicate, check that the expected answer does not leak into the input, and review a sample by hand. Tag every task with its source so results can be compared between synthetic and real data.

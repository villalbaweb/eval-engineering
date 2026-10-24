# Skills and progressive disclosure

A skill is a folder with a SKILL.md file holding a name, a one-line description and the full instructions. Progressive disclosure has three tiers: (1) only the name and description are in the system prompt, (2) the model calls a tool to load the skill, (3) extra files are read only when needed.

This avoids context bloat when many skills exist. The trade-off is one extra tool call of latency and the risk that the model fails to load the right skill, which is why skill selection must be evaluated.

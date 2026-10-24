# Tool design for agents (ACI)

Agent-computer interfaces deserve as much design effort as human interfaces. Make mistakes hard to make (poka-yoke): for example require absolute paths. Use strict schemas, clear descriptions with examples, and return concise, actionable error messages.

Limit an agent to roughly 5 to 15 tools; more tools degrade tool selection. Read-only tools can run in parallel while write tools should be serialized.

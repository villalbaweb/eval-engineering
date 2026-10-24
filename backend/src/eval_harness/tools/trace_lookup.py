from __future__ import annotations

from langchain_core.tools import tool

from eval_harness.storage.repositories import trials
from eval_harness.tools.base import register_tool


@register_tool(tags=("analysis", "readonly"))
@tool
def trace_lookup(trial_id: str = "latest") -> str:
    """Fetch a stored trial transcript by trial id (or 'latest'): the user request, each tool call with
    its arguments and result, the final answer and every grader verdict. Used for error analysis."""
    t = trials.latest() if trial_id == "latest" else trials.get(trial_id)
    if t is None:
        return f"No trial found for '{trial_id}'."
    lines = [f"trial={t.id} task={t.task_id} passed={t.passed} status={t.outcome.status}"]
    for tc in t.transcript.tool_calls:
        lines.append(f"- tool {tc.name}({tc.args}) -> {tc.result[:160]!r}{' [ERROR]' if tc.error else ''}")
    lines.append(f"skills_loaded={t.transcript.skills_loaded}")
    lines.append(f"final_answer={t.transcript.final_answer[:400]!r}")
    for g in t.grades:
        verdict = "skipped" if g.skipped else ("pass" if g.passed else "FAIL")
        lines.append(f"grader {g.grader}: {verdict} {g.rationale[:140]}")
    return "\n".join(lines)

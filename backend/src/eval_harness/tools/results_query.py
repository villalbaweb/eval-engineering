from __future__ import annotations

import json
from typing import Literal

from langchain_core.tools import tool

from eval_harness.storage.repositories import experiments
from eval_harness.tools.base import register_tool


@register_tool(tags=("analysis", "readonly"))
@tool
def results_query(
    experiment_id: str = "latest",
    section: Literal["overview", "by_tag", "by_grader", "flakiness", "cost_latency"] = "overview",
) -> str:
    """Read-only query over stored experiment summaries. section: overview (pass rate, CI, pass@k,
    pass^k), by_tag, by_grader, flakiness (flaky vs systematic failing tasks) or cost_latency."""
    exp_id = experiments.latest_id() if experiment_id == "latest" else experiment_id
    exp = experiments.get(exp_id) if exp_id else None
    if exp is None:
        return "No experiments found."
    s = exp.summary or {}
    if section == "overview":
        pr = {k: v for k, v in s.get("pass_rates", {}).items() if k != "per_task"}
        return json.dumps({"experiment": exp.id, "suite": exp.suite, "status": exp.status, **pr}, default=str)
    return json.dumps({"experiment": exp.id, section: s.get(section, {})}, default=str)

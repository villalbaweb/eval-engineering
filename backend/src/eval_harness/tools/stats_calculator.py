from __future__ import annotations

import json
from typing import Literal

from langchain_core.tools import tool

from eval_harness.evals.metrics import core
from eval_harness.tools.base import register_tool


@register_tool(tags=("math", "deterministic"))
@tool
def stats_calculator(
    operation: Literal["pass_at_k", "pass_pow_k", "bootstrap_ci", "wilson", "cohens_kappa", "two_proportion_z"],
    n: int | None = None,
    c: int | None = None,
    k: int | None = None,
    values: list[float] | None = None,
    a: list[bool] | None = None,
    b: list[bool] | None = None,
    s1: int | None = None, n1: int | None = None, s2: int | None = None, n2: int | None = None,
) -> str:
    """Exact evaluation statistics. Operations and their arguments:
    pass_at_k / pass_pow_k: n (trials), c (passed), k.
    bootstrap_ci: values (list of 0/1 or scores). wilson: c (successes), n.
    cohens_kappa: a and b (two equal-length boolean lists).
    two_proportion_z: s1, n1, s2, n2. Returns JSON."""
    try:
        if operation == "pass_at_k":
            r = {"pass_at_k": core.pass_at_k(n, c, k)}
        elif operation == "pass_pow_k":
            r = {"pass_pow_k": core.pass_pow_k(n, c, k), "pass_pow_k_exact": core.pass_pow_k_exact(n, c, k)}
        elif operation == "bootstrap_ci":
            m, lo, hi = core.bootstrap_ci(values or [])
            r = {"mean": m, "ci95": [lo, hi]}
        elif operation == "wilson":
            lo, hi = core.wilson_interval(c, n)
            r = {"rate": c / n if n else 0.0, "ci95": [lo, hi]}
        elif operation == "cohens_kappa":
            r = {"kappa": core.cohens_kappa(a or [], b or [])}
        else:
            z, p = core.two_proportion_z(s1, n1, s2, n2)
            r = {"z": z, "p_value": p}
        return json.dumps({k_: round(v, 6) if isinstance(v, float) else v for k_, v in r.items()})
    except Exception as e:
        return f"ERROR: invalid arguments for {operation}: {type(e).__name__}: {e}"

"""Experiment A/B comparison: per-task diff, significance, cost/latency deltas."""

from __future__ import annotations

from typing import Any

from eval_harness.evals.metrics import core
from eval_harness.evals.metrics.pass_rates import per_task_counts
from eval_harness.storage.repositories import experiments, trials


def compare(a_id: str, b_id: str, *, delta_threshold: float = 0.01) -> dict[str, Any]:
    ea, eb = experiments.get(a_id), experiments.get(b_id)
    if ea is None or eb is None:
        raise KeyError("experiment not found")
    ta, tb = trials.for_experiment(a_id), trials.for_experiment(b_id)
    ca, cb = per_task_counts(ta), per_task_counts(tb)
    common = sorted(set(ca) & set(cb))

    rows, regress, improve, same = [], [], [], []
    b_only_fail = a_only_fail = 0  # paired task-level (majority) outcomes for McNemar
    for tid in common:
        (na, pa), (nb, pb) = ca[tid], cb[tid]
        ra, rb = pa / na, pb / nb
        d = rb - ra
        row = {"task_id": tid, "a": ra, "b": rb, "delta": d, "n_a": na, "n_b": nb}
        rows.append(row)
        (improve if d > delta_threshold else regress if d < -delta_threshold else same).append(tid)
        a_pass, b_pass = ra >= 0.5, rb >= 0.5
        if a_pass and not b_pass:
            b_only_fail += 1
        if b_pass and not a_pass:
            a_only_fail += 1

    sa = sum(1 for t in ta if t.passed)
    sb = sum(1 for t in tb if t.passed)
    z, p_z = core.two_proportion_z(sa, len(ta), sb, len(tb))
    chi2, p_mc = core.mcnemar(b_only_fail, a_only_fail)

    def cl(e):
        return e.summary.get("cost_latency", {})

    return {
        "a": {"id": ea.id, "name": ea.name, "model": ea.snapshot.get("models", {}).get("agent", {}).get("model"),
              "pass_rate": sa / len(ta) if ta else 0.0, "n_trials": len(ta)},
        "b": {"id": eb.id, "name": eb.name, "model": eb.snapshot.get("models", {}).get("agent", {}).get("model"),
              "pass_rate": sb / len(tb) if tb else 0.0, "n_trials": len(tb)},
        "delta": (sb / len(tb) if tb else 0.0) - (sa / len(ta) if ta else 0.0),
        "two_proportion_z": {"z": z, "p_value": p_z},
        "mcnemar": {"chi2": chi2, "p_value": p_mc, "a_pass_b_fail": b_only_fail, "b_pass_a_fail": a_only_fail},
        "regressions": sorted(regress), "improvements": sorted(improve), "unchanged": len(same),
        "per_task": sorted(rows, key=lambda r: r["delta"]),  # regressions first
        "only_in_a": sorted(set(ca) - set(cb)), "only_in_b": sorted(set(cb) - set(ca)),
        "cost_latency": {"a": cl(ea), "b": cl(eb)},
        "config_diff": _config_diff(ea.snapshot, eb.snapshot),
    }


def _config_diff(a: dict, b: dict) -> dict[str, Any]:
    keys = ("models", "target", "tasks_hash", "git_sha")
    out = {}
    for k in keys:
        if a.get(k) != b.get(k):
            out[k] = {"a": a.get(k), "b": b.get(k)}
    return out

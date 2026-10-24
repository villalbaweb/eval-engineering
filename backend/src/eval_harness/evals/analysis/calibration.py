"""Grader calibration: compare each grader's verdicts with human labels (validate the validators)."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from eval_harness.evals.metrics import core
from eval_harness.storage.repositories import annotations, trials


def calibrate(experiment_id: str | None = None) -> dict[str, Any]:
    labels = {a.trial_id: a for a in annotations.all(experiment_id)}
    if not labels:
        return {"n_labeled": 0, "graders": {}, "trial_level": None,
                "message": "No human labels yet - label trials in the Annotate view."}
    pairs: dict[str, list[tuple[bool, bool, str]]] = defaultdict(list)
    overall: list[tuple[bool, bool, str]] = []
    exp_ids = {a.experiment_id for a in labels.values()}
    for exp_id in exp_ids:
        for t in trials.for_experiment(exp_id):
            lab = labels.get(t.id)
            if lab is None:
                continue
            overall.append((t.passed, lab.good, t.id))
            for g in t.grades:
                if g.skipped or g.passed is None or g.grader == "human_review":
                    continue
                pairs[g.grader].append((bool(g.passed), lab.good, t.id))

    def stats(items: list[tuple[bool, bool, str]]) -> dict[str, Any]:
        m = core.alignment([i[0] for i in items], [i[1] for i in items])
        m["disagreements"] = [{"trial_id": tid, "grader_pass": g, "human_good": h}
                              for g, h, tid in items if g != h]
        return {k: (None if isinstance(v, float) and v != v else v) for k, v in m.items()}

    return {
        "n_labeled": len(labels),
        "trial_level": stats(overall) if overall else None,
        "graders": {name: stats(items) for name, items in sorted(pairs.items())},
        "failure_tags": _tag_counts(labels.values()),
    }


def _tag_counts(rows) -> dict[str, int]:
    out: dict[str, int] = defaultdict(int)
    for r in rows:
        if not r.good:
            for tag in filter(None, r.failure_tags.split(",")):
                out[tag] += 1
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))

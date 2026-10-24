from __future__ import annotations

from typing import Any

from eval_harness.evals.data_sources import quality, review
from eval_harness.evals.data_sources.synthesis.base import generator_registry, load_config


def run_synthesis(config_name: str, *, accept: bool = False, group: str = "synthetic") -> dict[str, Any]:
    """Generate candidates from ``evals/synthesis/<config>.yaml`` and queue them for review."""
    cfg = load_config(config_name)
    gen = generator_registry.get(cfg.generator)(cfg)
    tasks = gen.generate()
    res = review.save_candidates(tasks)
    res["generated"] = len(tasks)
    res["diversity"] = quality.diversity(tasks, list(cfg.dimensions)) if cfg.dimensions else {}
    if accept:
        res["accepted"] = review.accept(res["ids"], group=group)
    return res

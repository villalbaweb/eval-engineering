from __future__ import annotations

from fastapi import APIRouter, HTTPException

from eval_harness.evals.analysis.compare import compare as do_compare

router = APIRouter(tags=["compare"])


@router.get("/compare")
def compare(a: str, b: str) -> dict:
    try:
        return do_compare(a, b)
    except KeyError as e:
        raise HTTPException(404, "experiment not found") from e

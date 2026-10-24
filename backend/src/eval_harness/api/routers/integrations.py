from __future__ import annotations

import asyncio

from fastapi import APIRouter

from eval_harness.core.settings import get_settings
from eval_harness.evals.datasets.loader import load_tasks
from eval_harness.integrations.langsmith.client import enabled
from eval_harness.integrations.langsmith.datasets import pull_dataset, push_tasks

router = APIRouter(tags=["integrations"])


@router.get("/integrations/langsmith")
def status() -> dict:
    s = get_settings()
    return {"enabled": enabled(), "has_key": bool(s.langsmith_api_key), "tracing": s.langsmith_tracing,
            "project": s.langsmith_project}


@router.post("/integrations/langsmith/datasets/{group}/push")
async def push(group: str) -> dict:
    res = await asyncio.to_thread(push_tasks, group, load_tasks([group]))
    return res or {"error": "LangSmith disabled or push failed"}


@router.post("/integrations/langsmith/datasets/{name}/pull")
async def pull(name: str) -> dict:
    p = await asyncio.to_thread(pull_dataset, name)
    return {"file": str(p)} if p else {"error": "LangSmith disabled or pull failed"}

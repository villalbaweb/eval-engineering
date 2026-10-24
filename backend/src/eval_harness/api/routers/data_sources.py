from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from eval_harness.core.settings import get_settings
from eval_harness.evals.data_sources import review
from eval_harness.evals.data_sources.synthesis.runner import run_synthesis
from eval_harness.evals.data_sources.traces.importer import import_traces
from eval_harness.evals.data_sources.traffic.simulator import simulate_traffic

router = APIRouter(tags=["data-sources"])


@router.get("/synthesis/configs")
def configs() -> list[str]:
    return [p.stem for p in sorted(get_settings().synthesis_dir.glob("*.yaml"))]


class SynthesisBody(BaseModel):
    config: str
    accept: bool = False


@router.post("/synthesis/run")
async def synthesize(body: SynthesisBody) -> dict:
    try:
        return await asyncio.to_thread(run_synthesis, body.config, accept=body.accept)
    except (FileNotFoundError, KeyError, ValueError) as e:
        raise HTTPException(400, str(e)) from e


class TrafficBody(BaseModel):
    n: int = 10
    agent: str = "copilot-baseline"
    fault_rate: float = 0.0


@router.post("/traffic/simulate")
async def traffic(body: TrafficBody) -> dict:
    return await simulate_traffic(n=body.n, agent=body.agent, fault_rate=body.fault_rate)


class ImportBody(BaseModel):
    adapter: str | None = None
    limit: int = 50
    source: str | None = None
    errors_only: bool = False


@router.post("/traces/import")
async def traces(body: ImportBody) -> dict:
    from eval_harness.integrations.langsmith.client import enabled

    adapter = body.adapter or ("langsmith" if enabled() else "jsonl")
    try:
        return await asyncio.to_thread(import_traces, adapter, limit=body.limit, source=body.source,
                                       errors_only=body.errors_only)
    except (RuntimeError, KeyError) as e:
        raise HTTPException(400, str(e)) from e


@router.get("/candidates")
def candidates() -> list[dict]:
    return [c.model_dump(mode="json", exclude={"metadata"}) | {
        "has_transcript": "transcript" in c.metadata,
        "thumbs": c.metadata.get("feedback", {}).get("thumbs")} for c in review.list_candidates()]


class AcceptBody(BaseModel):
    ids: list[str]
    group: str = "accepted"


@router.post("/candidates/accept")
def accept(body: AcceptBody) -> dict:
    return review.accept(body.ids, group=body.group)


@router.post("/candidates/reject")
def reject(body: AcceptBody) -> dict:
    return {"rejected": review.reject(body.ids)}


class PatchBody(BaseModel):
    patch: dict


@router.patch("/candidates/{cid}")
def patch(cid: str, body: PatchBody) -> dict:
    try:
        return review.update_candidate(cid, body.patch).model_dump(mode="json", exclude={"metadata"})
    except KeyError as e:
        raise HTTPException(404) from e

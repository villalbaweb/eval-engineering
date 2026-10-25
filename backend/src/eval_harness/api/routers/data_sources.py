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
    agent: str | None = None  # variant (or legacy agent name); default: the profile's default variant
    variant: str | None = None
    fault_rate: float = 0.0


@router.post("/traffic/simulate")
async def traffic(body: TrafficBody) -> dict:
    from eval_harness.profiles import VariantNotFound

    try:
        return await simulate_traffic(n=body.n, agent=body.variant or body.agent, fault_rate=body.fault_rate)
    except (ValueError, VariantNotFound) as e:
        raise HTTPException(400, str(e)) from e


class ImportBody(BaseModel):
    adapter: str | None = None
    limit: int = 50
    source: str | None = None
    errors_only: bool = False


@router.post("/traces/import")
async def traces(body: ImportBody) -> dict:
    from eval_harness.evals.data_sources.traces.importer import default_adapter

    adapter = body.adapter or default_adapter()
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
    chosen = [c for c in review.list_candidates() if body.ids == ["all"] or c.id in set(body.ids)]
    return {**review.accept(body.ids, group=body.group), "warnings": _inventory_warnings(chosen)}


def _inventory_warnings(tasks: list) -> list[str]:
    from eval_harness.profiles import active_profile
    from eval_harness.profiles.inventory import expectation_warnings

    return expectation_warnings(tasks, active_profile())


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


@router.get("/candidates/{cid}/yaml")
def candidate_yaml(cid: str) -> dict:
    try:
        return {"id": cid, "content": review.candidate_yaml(cid)}
    except KeyError as e:
        raise HTTPException(404) from e


class YamlBody(BaseModel):
    content: str


@router.put("/candidates/{cid}/yaml")
def save_candidate_yaml(cid: str, body: YamlBody) -> dict:
    """Edit a candidate before accepting it (typically: add ``expected``). The transcript is preserved."""
    try:
        t = review.save_candidate_yaml(cid, body.content)
    except KeyError as e:
        raise HTTPException(404) from e
    except Exception as e:  # yaml / validation errors -> show the reason in the editor
        raise HTTPException(422, f"invalid task: {e}") from e
    return {"saved": t.id, "warnings": _inventory_warnings([t])}

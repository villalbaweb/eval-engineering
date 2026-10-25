from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from eval_harness.api.events import bus
from eval_harness.evals.runner.service import prepare_regrade, prepare_runner
from eval_harness.storage.repositories import experiments, task_snapshots, trials

router = APIRouter(tags=["experiments"])


class LaunchRequest(BaseModel):
    suite: str
    name: str | None = None
    agent: str | None = None
    k: int | None = None
    concurrency: int | None = None
    tool_mode: str | None = None
    target: str | None = None
    max_tasks: int | None = None
    graders: list[dict[str, Any]] | None = None
    datasets: list[str] | None = None  # run these dataset groups with the suite's graders/target
    model: str | None = None  # "provider:model" override for the agent (model sweeps)


@router.post("/experiments")
async def launch(req: LaunchRequest) -> dict:
    overrides = req.model_dump(exclude={"suite", "name", "model"})
    try:
        runner = prepare_runner(req.suite, overrides=overrides, name=req.name)
        if req.model:
            _apply_model(runner, req.model)
    except (FileNotFoundError, ValueError, KeyError) as e:
        raise HTTPException(400, str(e)) from e
    return {"id": bus.launch(runner), "total": runner.exp.total_trials}


def _apply_model(runner, spec: str) -> None:
    provider, _, name = spec.partition(":")
    cfg = getattr(runner.target, "cfg", None)
    if cfg is None:
        raise ValueError("model override needs an agent-based target")
    cfg.model.provider, cfg.model.name = provider, name
    runner.exp.snapshot = runner._snapshot({"model_override": spec})


@router.get("/experiments")
def list_experiments(limit: int = 100) -> list[dict]:
    return [e.model_dump(mode="json", exclude={"snapshot"}) | {
        "model": e.snapshot.get("models", {}).get("agent", {}).get("model"),
        "agent": e.snapshot.get("target", {}).get("agent_config", {}).get("name"),
        "datasets": e.snapshot.get("suite", {}).get("datasets")} for e in experiments.list(limit)]


@router.get("/experiments/{exp_id}")
def get_experiment(exp_id: str) -> dict:
    e = experiments.get(exp_id)
    if e is None:
        raise HTTPException(404)
    return e.model_dump(mode="json")


@router.get("/experiments/{exp_id}/events")
async def events(exp_id: str):
    if experiments.get(exp_id) is None:
        raise HTTPException(404)

    async def gen():
        live = exp_id in bus.runners or exp_id in bus.history
        if not live:  # finished before this server started: synthesize the terminal event
            e = experiments.get(exp_id)
            yield {"event": "experiment_done", "data": json.dumps({"type": "experiment_done", "status": e.status})}
            return
        async for ev in bus.subscribe(exp_id):
            yield {"event": ev["type"], "data": json.dumps(ev, default=str)}

    return EventSourceResponse(gen())


@router.get("/experiments/{exp_id}/trials")
def list_trials(exp_id: str) -> list[dict]:
    tasks = task_snapshots.for_experiment(exp_id)
    out = []
    for t in sorted(trials.for_experiment(exp_id), key=lambda x: (x.task_id, x.index)):
        task = tasks.get(t.task_id)
        out.append({
            "id": t.id, "task_id": t.task_id, "index": t.index, "passed": t.passed, "status": t.outcome.status,
            "error": t.outcome.error, "duration_s": t.duration_s, "tags": task.tags if task else [],
            "source": task.source if task else None, "user_text": task.user_text if task else "",
            "grades": [{"grader": g.grader, "passed": g.passed, "skipped": g.skipped, "score": g.score,
                        "layer": g.layer} for g in t.grades],
            "skills_loaded": t.transcript.skills_loaded, "tools": t.transcript.tool_names,
            "answer": t.transcript.final_answer[:300]})
    return out


@router.get("/trials/{trial_id}")
def get_trial(trial_id: str) -> dict:
    t = trials.get(trial_id)
    if t is None:
        raise HTTPException(404)
    task = task_snapshots.for_experiment(t.experiment_id).get(t.task_id)
    return {"trial": t.model_dump(mode="json"), "task": task.model_dump(mode="json") if task else None,
            "passed": t.passed}


@router.post("/experiments/{exp_id}/cancel")
def cancel(exp_id: str) -> dict:
    r = bus.runners.get(exp_id)
    if r is None:
        raise HTTPException(404, "experiment is not running")
    r.cancel()
    return {"cancelling": True}


class RegradeRequest(BaseModel):
    suite: str | None = None
    graders: list[dict[str, Any]] | None = None
    name: str | None = None


@router.post("/experiments/{exp_id}/regrade")
async def regrade(exp_id: str, req: RegradeRequest) -> dict:
    """Re-grade stored transcripts with current/changed graders - the agent is NOT re-run."""
    try:
        runner = prepare_regrade(exp_id, suite_name=req.suite, graders=req.graders, name=req.name)
    except (KeyError, ValueError, FileNotFoundError) as e:
        raise HTTPException(400, str(e)) from e
    return {"id": bus.launch(runner), "total": runner.exp.total_trials}

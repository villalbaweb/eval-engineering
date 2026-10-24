from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from eval_harness.evals.analysis.calibration import calibrate
from eval_harness.integrations.langsmith.client import get_client, safe
from eval_harness.storage.repositories import annotations, task_snapshots, trials

router = APIRouter(tags=["annotations"])


class AnnotationBody(BaseModel):
    trial_id: str
    good: bool
    failure_tags: list[str] = []
    note: str = ""


@safe
def _ls(run_id: str, good: bool, tags: list[str], note: str) -> None:
    get_client().create_feedback(run_id, key="human_good", score=1.0 if good else 0.0,
                                 comment=(note + " " + ",".join(tags)).strip())


@router.post("/annotations")
def annotate(body: AnnotationBody) -> dict:
    t = trials.get(body.trial_id)
    if t is None:
        raise HTTPException(404, "trial not found")
    row = annotations.upsert(body.trial_id, t.experiment_id, body.good, body.failure_tags, body.note)
    if run_id := t.transcript.meta.get("langsmith_run_id"):
        _ls(run_id, body.good, body.failure_tags, body.note)
    return {"id": row.id}


@router.get("/annotations/queue")
def queue(experiment_id: str, only_unlabeled: bool = True, limit: int = 50) -> list[dict]:
    labelled = {a.trial_id: a for a in annotations.all(experiment_id)}
    tasks = task_snapshots.for_experiment(experiment_id)
    out = []
    for t in trials.for_experiment(experiment_id):
        if only_unlabeled and t.id in labelled:
            continue
        task = tasks.get(t.task_id)
        out.append({"trial_id": t.id, "task_id": t.task_id, "user_text": task.user_text if task else "",
                    "answer": t.transcript.final_answer, "tools": t.transcript.tool_names,
                    "skills": t.transcript.skills_loaded, "passed": t.passed,
                    "labeled": t.id in labelled, "good": labelled[t.id].good if t.id in labelled else None,
                    "failure_tags": labelled[t.id].failure_tags if t.id in labelled else "",
                    "grades": [{"grader": g.grader, "passed": g.passed, "skipped": g.skipped} for g in t.grades]})
    return out[:limit]


@router.get("/calibration")
def calibration(experiment_id: str | None = None) -> dict:
    return calibrate(experiment_id)

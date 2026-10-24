from __future__ import annotations

from pathlib import Path

import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from eval_harness.core.settings import get_settings
from eval_harness.evals.datasets.loader import _read_tasks, dataset_files, list_suites, load_tasks
from eval_harness.evals.domain.task import Task

router = APIRouter(tags=["datasets"])


def _safe(root: Path, rel: str) -> Path:
    p = (root / rel).resolve()
    if root.resolve() not in p.parents and p != root.resolve():
        raise HTTPException(400, "path escapes the evals folder")
    return p


@router.get("/datasets/tasks")
def tasks(group: str | None = None, tag: str | None = None) -> list[dict]:
    ts = load_tasks([group] if group else None, include_tags=[tag] if tag else None)
    return [t.model_dump(mode="json", exclude={"metadata"} | ({"input"} if False else set())) | {
        "has_transcript": "transcript" in t.metadata} for t in ts]


@router.get("/datasets/files")
def files() -> list[str]:
    root = get_settings().datasets_dir
    return [f.relative_to(root).as_posix() for f in dataset_files()]


@router.get("/datasets/files/{path:path}")
def read_file(path: str) -> dict:
    p = _safe(get_settings().datasets_dir, path)
    if not p.exists():
        raise HTTPException(404)
    return {"path": path, "content": p.read_text(encoding="utf-8")}


class SaveBody(BaseModel):
    content: str


@router.put("/datasets/files/{path:path}")
def save_file(path: str, body: SaveBody) -> dict:
    """Validate the YAML as tasks, then save. Invalid content is rejected with the reason."""
    p = _safe(get_settings().datasets_dir, path)
    if p.suffix not in (".yaml", ".yml"):
        raise HTTPException(400, "only .yaml files can be edited")
    try:
        data = yaml.safe_load(body.content)
        raw = data.get("tasks", []) if isinstance(data, dict) else (data or [])
        parsed = [Task.model_validate(x) for x in raw]
    except Exception as e:
        raise HTTPException(422, f"invalid task file: {e}") from e
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body.content, encoding="utf-8")
    return {"saved": path, "tasks": len(parsed)}


@router.get("/suites/{name}")
def suite_yaml(name: str) -> dict:
    p = get_settings().suites_dir / f"{name}.yaml"
    if not p.exists():
        raise HTTPException(404)
    suite = next(s for s in list_suites() if s.name == name)
    return {"yaml": p.read_text(encoding="utf-8"), "n_tasks": len(load_tasks(suite.datasets,
            include_tags=suite.include_tags, exclude_tags=suite.exclude_tags, kinds=suite.kinds))}


@router.get("/rubrics")
def rubrics() -> dict:
    d = get_settings().rubrics_dir
    return {p.stem: p.read_text(encoding="utf-8") for p in sorted(d.glob("*.md"))}


_ = _read_tasks  # re-exported for tests

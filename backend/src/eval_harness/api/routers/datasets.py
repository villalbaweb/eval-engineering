from __future__ import annotations

import re
from pathlib import Path

import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from eval_harness.core.settings import get_settings
from eval_harness.evals.datasets.loader import (
    _read_tasks,
    dataset_files,
    load_suite,
    load_tasks,
    parse_suite,
    validate_suite_refs,
)
from eval_harness.evals.domain.suite import Suite
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
    return {"saved": path, "tasks": len(parsed), "warnings": _inventory_warnings(parsed)}


def _inventory_warnings(tasks: list[Task]) -> list[str]:
    from eval_harness.profiles import active_profile
    from eval_harness.profiles.inventory import expectation_warnings

    return expectation_warnings(tasks, active_profile())


_NAME = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


def _n_tasks(suite: Suite) -> int:
    return len(load_tasks(suite.datasets, include_tags=suite.include_tags, exclude_tags=suite.exclude_tags,
                          kinds=suite.kinds))


@router.get("/suites/{name}")
def suite_yaml(name: str) -> dict:
    p = get_settings().suites_dir / f"{name}.yaml"
    if not _NAME.match(name) or not p.exists():
        raise HTTPException(404)
    return {"yaml": p.read_text(encoding="utf-8"), "n_tasks": _n_tasks(load_suite(name))}


@router.put("/suites/{name}")
def save_suite(name: str, body: SaveBody) -> dict:
    """Create or replace ``evals/suites/<name>.yaml``. Rejected unless it parses, its ``name`` matches
    the file, and every grader/target/agent it names exists. Selecting 0 tasks is allowed (warned)."""
    if not _NAME.match(name):
        raise HTTPException(400, "suite names are lowercase letters, digits, '-' and '_'")
    try:
        data = yaml.safe_load(body.content)
        suite = parse_suite(data, name=name)
    except Exception as e:
        raise HTTPException(422, f"invalid suite: {e}") from e
    if suite.name != name:
        raise HTTPException(422, f"'name: {suite.name}' must match the file name '{name}'")
    errs = validate_suite_refs(suite)
    try:
        n = _n_tasks(suite)
    except ValueError as e:  # e.g. duplicate task ids across the selected datasets
        errs.append(str(e))
        n = 0
    if errs:
        raise HTTPException(422, "; ".join(errs))
    p = get_settings().suites_dir / f"{name}.yaml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body.content, encoding="utf-8")
    return {"saved": name, "n_tasks": n, "warning": None if n else "this suite selects no tasks yet"}


@router.get("/faults")
def faults() -> list[str]:
    return [p.stem for p in sorted(get_settings().faults_dir.glob("*.yaml"))]


@router.get("/rubrics")
def rubrics() -> dict:
    """Shared rubrics overlaid with the active profile's own (same name: the profile's wins)."""
    s = get_settings()
    out: dict[str, str] = {}
    for d in dict.fromkeys((s.shared_rubrics_dir, s.rubrics_dir)):
        out.update({p.stem: p.read_text(encoding="utf-8") for p in sorted(d.glob("*.md"))})
    return dict(sorted(out.items()))


_ = _read_tasks  # re-exported for tests

"""Candidate review queue.

Imported traces and synthetic tasks both land in ``evals/candidates/`` as one YAML file per task.
Nothing becomes part of a dataset until a human accepts it (UI or ``evalh candidates --accept``).
"""

from __future__ import annotations

from typing import Any

import yaml

from eval_harness.core.settings import get_settings
from eval_harness.evals.data_sources import quality
from eval_harness.evals.domain.task import Task


def _dir():
    d = get_settings().candidates_dir
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_candidates(tasks: list[Task], *, existing: list[Task] | None = None) -> dict[str, Any]:
    """Quality-gate and queue candidates. Returns counts and what was dropped (and why)."""
    from eval_harness.evals.datasets.loader import load_tasks

    known = (existing if existing is not None else load_tasks()) + list_candidates()
    scrubbed = [quality.scrub_task(t) for t in tasks]
    leaked = [t.id for t in scrubbed if quality.leaks(t)]
    scrubbed = [t for t in scrubbed if t.id not in leaked]
    kept, dups = quality.dedupe(scrubbed, known)
    for t in kept:
        (_dir() / f"{t.id}.yaml").write_text(
            yaml.safe_dump(t.model_dump(mode="json", exclude_defaults=True), sort_keys=False, allow_unicode=True),
            encoding="utf-8")
    return {"queued": len(kept), "duplicates_dropped": len(dups), "leaks_dropped": len(leaked),
            "ids": [t.id for t in kept]}


def list_candidates() -> list[Task]:
    out = []
    for f in sorted(_dir().glob("*.yaml")):
        out.append(Task.model_validate(yaml.safe_load(f.read_text(encoding="utf-8"))))
    return out


def get_candidate(cid: str) -> Task | None:
    f = _dir() / f"{cid}.yaml"
    return Task.model_validate(yaml.safe_load(f.read_text(encoding="utf-8"))) if f.exists() else None


def update_candidate(cid: str, patch: dict[str, Any]) -> Task:
    cur = get_candidate(cid)
    if cur is None:
        raise KeyError(cid)
    new = Task.model_validate({**cur.model_dump(mode="json"), **patch, "id": cid})
    (_dir() / f"{cid}.yaml").write_text(
        yaml.safe_dump(new.model_dump(mode="json", exclude_defaults=True), sort_keys=False, allow_unicode=True),
        encoding="utf-8")
    return new


def candidate_yaml(cid: str) -> str:
    """The candidate as editable YAML. The logged transcript is hidden (large, not meant for hand
    edits) and kept untouched by :func:`save_candidate_yaml`."""
    cur = get_candidate(cid)
    if cur is None:
        raise KeyError(cid)
    data = cur.model_dump(mode="json", exclude_defaults=True)
    meta = {k: v for k, v in data.get("metadata", {}).items() if k != "transcript"}
    data.pop("metadata", None)
    if meta:
        data["metadata"] = meta
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True)


def save_candidate_yaml(cid: str, text: str) -> Task:
    cur = get_candidate(cid)
    if cur is None:
        raise KeyError(cid)
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError("expected a YAML mapping (one task)")
    if data.get("id", cid) != cid:
        raise ValueError("the id cannot be changed here (reject and re-import instead)")
    meta = dict(data.get("metadata") or {})
    if "transcript" in cur.metadata:
        meta["transcript"] = cur.metadata["transcript"]
    new = Task.model_validate({**data, "id": cid, "metadata": meta})
    (_dir() / f"{cid}.yaml").write_text(
        yaml.safe_dump(new.model_dump(mode="json", exclude_defaults=True), sort_keys=False, allow_unicode=True),
        encoding="utf-8")
    return new


def reject(ids: list[str]) -> int:
    n = 0
    for cid in ids:
        f = _dir() / f"{cid}.yaml"
        if f.exists():
            f.unlink()
            n += 1
    return n


def accept(ids: list[str], *, group: str = "accepted") -> dict[str, Any]:
    """Move candidates into ``evals/datasets/<group>/<group>.yaml`` (appending)."""
    cands = list_candidates()
    chosen = cands if ids == ["all"] else [c for c in cands if c.id in set(ids)]
    if not chosen:
        return {"accepted": 0}
    target = get_settings().datasets_dir / group / f"{group}.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    existing: list[dict] = []
    if target.exists():
        data = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
        existing = data.get("tasks", [])
    have = {t["id"] for t in existing}
    add = []
    for c in chosen:
        # keep datasets small, except logged traces: the 'trace' target needs the transcript to grade it
        keep_transcript = c.source.startswith("traces:")
        meta = {k: v for k, v in c.metadata.items() if k != "transcript" or keep_transcript}
        add.append(c.model_copy(update={"metadata": meta}).model_dump(mode="json", exclude_defaults=True))
    new = [t for t in add if t["id"] not in have]
    target.write_text(yaml.safe_dump({"tasks": existing + new}, sort_keys=False, allow_unicode=True), encoding="utf-8")
    reject([c.id for c in chosen])
    return {"accepted": len(new), "file": str(target)}

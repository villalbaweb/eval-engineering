"""Sync local YAML tasks <-> LangSmith datasets. The local YAML stays the source of truth."""

from __future__ import annotations

from pathlib import Path

import yaml

from eval_harness.core.settings import get_settings
from eval_harness.evals.domain.task import Task
from eval_harness.integrations.langsmith.client import get_client, safe

PREFIX = "eval-eng/"  # the lab's default; a profile can set its own (defaults.langsmith_prefix)


def prefix() -> str:
    """``<profile langsmith_prefix>/``, or the legacy ``eval-eng/`` (so existing datasets keep their names)."""
    from eval_harness.profiles import active_profile

    p = active_profile().defaults.langsmith_prefix
    return f"{p.rstrip('/')}/" if p else PREFIX


def dataset_name(group: str) -> str:
    pre = prefix()
    return group if group.startswith(pre) else pre + group


@safe
def push_tasks(group: str, tasks: list[Task]) -> dict:
    """Create the dataset if needed and add tasks that are not there yet (matched by task_id)."""
    c = get_client()
    name = dataset_name(group)
    ds = c.read_dataset(dataset_name=name) if c.has_dataset(dataset_name=name) else c.create_dataset(
        dataset_name=name, description=f"Local eval tasks for '{group}' (managed by eval-harness)")
    existing = {(e.metadata or {}).get("task_id"): e.id for e in c.list_examples(dataset_id=ds.id)}
    new = [t for t in tasks if t.id not in existing]
    if new:
        c.create_examples(
            dataset_id=ds.id,
            inputs=[t.input for t in new],
            outputs=[t.expected.model_dump(mode="json") for t in new],
            metadata=[{"task_id": t.id, "kind": t.kind, "tags": t.tags, "source": t.source} for t in new],
        )
    ids = {**existing}
    if new:
        ids = {(e.metadata or {}).get("task_id"): e.id for e in c.list_examples(dataset_id=ds.id)}
    return {"dataset_id": str(ds.id), "dataset_name": name, "added": len(new), "total": len(ids),
            "example_ids": {k: str(v) for k, v in ids.items()}}


@safe
def pull_dataset(name: str, out_group: str = "langsmith") -> Path:
    """Write a LangSmith dataset to ``evals/datasets/<out_group>/<name>.yaml``."""
    from eval_harness.evals.domain.task import Expected

    c = get_client()
    tasks = []
    for i, e in enumerate(c.list_examples(dataset_name=dataset_name(name))):
        md = e.metadata or {}
        tasks.append(Task(
            id=md.get("task_id") or f"ls-{i:03d}", kind=md.get("kind", "regression"), tags=md.get("tags", []),
            input=e.inputs or {}, expected=Expected.model_validate(e.outputs or {}),
            source=f"langsmith:{name}").model_dump(mode="json", exclude_defaults=True))
    out = get_settings().datasets_dir / out_group / f"{name.replace('/', '_')}.yaml"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(yaml.safe_dump({"tasks": tasks}, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return out

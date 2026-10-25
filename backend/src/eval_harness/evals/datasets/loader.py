"""Load tasks and suites from ``evals/`` (YAML / JSONL). Content is data; no Python needed."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from eval_harness.core.settings import get_settings
from eval_harness.evals.domain.suite import Suite
from eval_harness.evals.domain.task import Task


def _read_tasks(path: Path) -> list[Task]:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".jsonl":
        raw = [json.loads(line) for line in text.splitlines() if line.strip()]
    else:
        data = yaml.safe_load(text)
        raw = data.get("tasks", []) if isinstance(data, dict) and "tasks" in data else (
            data if isinstance(data, list) else [data])
    tasks = []
    for item in raw:
        if not item:
            continue
        try:
            tasks.append(Task.model_validate(item))
        except Exception as e:
            raise ValueError(f"{path}: invalid task {item.get('id', '?')}: {e}") from e
    return tasks


def dataset_files(patterns: list[str] | None = None) -> list[Path]:
    root = get_settings().datasets_dir
    if not patterns:
        patterns = ["**/*.yaml", "**/*.yml", "**/*.jsonl"]
    files: list[Path] = []
    for pat in patterns:
        p = root / pat
        if p.is_file():
            files.append(p)
        elif p.is_dir():
            files += [f for ext in ("yaml", "yml", "jsonl") for f in sorted(p.rglob(f"*.{ext}"))]
        else:
            files += [f for f in sorted(root.glob(pat)) if f.is_file()]
    seen, out = set(), []
    for f in files:
        if f not in seen:
            seen.add(f)
            out.append(f)
    return out


def load_tasks(patterns: list[str] | None = None, *, include_tags: list[str] | None = None,
               exclude_tags: list[str] | None = None, kinds: list[str] | None = None,
               max_tasks: int | None = None) -> list[Task]:
    tasks: list[Task] = []
    ids: dict[str, Path] = {}
    for f in dataset_files(patterns):
        for t in _read_tasks(f):
            if t.id in ids:
                raise ValueError(f"duplicate task id '{t.id}' in {f} and {ids[t.id]}")
            ids[t.id] = f
            tasks.append(t)
    if include_tags:
        tasks = [t for t in tasks if set(t.tags) & set(include_tags)]
    if exclude_tags:
        tasks = [t for t in tasks if not set(t.tags) & set(exclude_tags)]
    if kinds:
        tasks = [t for t in tasks if t.kind in kinds]
    return tasks[:max_tasks] if max_tasks else tasks


def dataset_groups() -> dict[str, int]:
    """Folder name -> number of tasks (for the UI / CLI listing)."""
    root = get_settings().datasets_dir
    out: dict[str, int] = {}
    for f in dataset_files():
        group = f.relative_to(root).parts[0] if len(f.relative_to(root).parts) > 1 else f.stem
        out[group] = out.get(group, 0) + len(_read_tasks(f))
    return dict(sorted(out.items()))


def load_suite(name: str) -> Suite:
    p = get_settings().suites_dir / f"{name}.yaml"
    if not p.exists():
        raise FileNotFoundError(f"suite '{name}' not found. Available: {[s.name for s in list_suites()]}")
    return parse_suite(yaml.safe_load(p.read_text(encoding="utf-8")), name=name)


def parse_suite(data: Any, *, name: str) -> Suite:
    suite = Suite.model_validate(data)
    keys = [g.key for g in suite.graders]
    if len(set(keys)) != len(keys):
        raise ValueError(f"suite '{name}' has duplicate grader names: {keys}")
    return suite


def validate_suite_refs(suite: Suite) -> list[str]:
    """Problems a suite file can parse with but cannot run with (unknown grader/target/agent)."""
    from eval_harness.agent.config import list_agent_configs
    from eval_harness.evals.graders.base import grader_registry
    from eval_harness.evals.targets.base import target_registry

    errs = [f"unknown grader type '{g.type}'" for g in suite.graders if g.type not in grader_registry]
    if suite.target not in target_registry:
        errs.append(f"unknown target '{suite.target}' (have {target_registry.names()})")
    if suite.agent not in {a.name for a in list_agent_configs()}:
        errs.append(f"unknown agent '{suite.agent}'")
    return errs


def list_suites() -> list[Suite]:
    return [load_suite(p.stem) for p in sorted(get_settings().suites_dir.glob("*.yaml"))]


def suite_tasks(suite: Suite) -> list[Task]:
    return load_tasks(suite.datasets, include_tags=suite.include_tags, exclude_tags=suite.exclude_tags,
                      kinds=suite.kinds, max_tasks=suite.run.max_tasks)

"""Test helpers: point settings at a private evals/ copy and create a second, trace-only agent profile."""

from __future__ import annotations

import contextlib
import json
import shutil
from collections.abc import Iterator
from pathlib import Path

import yaml

from eval_harness.core.settings import get_settings


@contextlib.contextmanager
def private_evals(src: Path, dst: Path) -> Iterator[Path]:
    shutil.copytree(src, dst)
    s = get_settings()
    old = s.evals_dir
    s.evals_dir = dst
    try:
        yield dst
    finally:
        s.evals_dir = old


def logged_transcript(question: str, skill: str, failing_tool: bool) -> dict:
    """A message-only transcript in the demo agent's own conventions."""
    calls = [{"id": "c1", "type": "function", "function": {"name": "use_capability",
                                                            "arguments": json.dumps({"name": skill})}},
             {"id": "c2", "type": "function", "function": {"name": "search_orders", "arguments": "{}"}}]
    return {"messages": [
        {"role": "user", "content": question},
        {"role": "assistant", "content": "", "tool_calls": calls},
        {"role": "tool", "tool_call_id": "c1", "content": "capability loaded"},
        {"role": "tool", "tool_call_id": "c2",
         "content": json.dumps({"error": "orders service timeout"} if failing_tool else {"orders": [1, 2]})},
        {"role": "assistant", "content": "Here is the answer."}]}


def make_demo_profile(evals: Path, name: str = "demo") -> Path:
    root = evals / "profiles" / name
    for d in ("variants", "datasets/logged", "suites", "candidates", "traces"):
        (root / d).mkdir(parents=True, exist_ok=True)
    (root / "profile.yaml").write_text(yaml.safe_dump({
        "description": "Second agent: only its logged runs are available.",
        "default_variant": "prod-traces",
        "inventory": {"tools": [{"name": "search_orders"}], "skills": [{"name": "refunds"}, {"name": "returns"}]},
        "conventions": {"skills": [{"tool": "use_capability", "arg": "name"}],
                        "tool_error": [{"result_json_key": "error"}], "citations": None},
        "traces": {"adapter": "jsonl", "path": "traces"},
        "defaults": {"quick_suite": "traces", "trace_suite": "traces", "trace_group": "logged",
                     "langsmith_prefix": f"{name}-agent"},
    }), encoding="utf-8")
    (root / "variants" / "prod-traces.yaml").write_text(yaml.safe_dump(
        {"description": "read-only production logs", "target": "trace_source"}), encoding="utf-8")
    (root / "suites" / "traces.yaml").write_text(yaml.safe_dump({
        "name": "traces", "mode": "trace", "datasets": ["logged"],
        "graders": [{"type": "tool_errors"}, {"type": "citation_grounding"}, {"type": "skill_selection"}],
        "run": {"k": 1, "fail_fast": False}}), encoding="utf-8")
    tasks = []
    for i, (q, skill, bad) in enumerate([("refund my order", "refunds", False), ("return item", "returns", True)]):
        from eval_harness.evals.data_sources.traces.base import transcript_from_messages
        from eval_harness.evals.domain.profile import Profile

        conv = Profile.model_validate({"name": name, **yaml.safe_load((root / "profile.yaml").read_text())}).conventions
        raw = logged_transcript(q, skill, bad)
        t = transcript_from_messages(raw["messages"], conventions=conv)
        tasks.append({"id": f"logged-{i}", "input": {"messages": raw["messages"][:1]},
                      "expected": {"skills_loaded": [skill]}, "metadata": {"transcript": t.model_dump(mode="json")}})
    (root / "datasets" / "logged" / "logged.yaml").write_text(yaml.safe_dump({"tasks": tasks}), encoding="utf-8")
    # an exported JSONL with message-only records (the importer derives tool calls with the conventions)
    recs = [{"id": f"run-{i}", "source": "prod", "input_messages": logged_transcript(q, s, b)["messages"][:1],
             "transcript": {"messages": logged_transcript(q, s, b)["messages"]}}
            for i, (q, s, b) in enumerate([("cancel order", "refunds", True), ("track parcel", "returns", False)])]
    (root / "traces" / "export.jsonl").write_text("\n".join(json.dumps(r) for r in recs) + "\n", encoding="utf-8")
    return root

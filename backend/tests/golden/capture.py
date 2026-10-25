"""Golden baseline for the agent-profiles decoupling (see .agents/AGENT_PROFILES_PLAN.md, section 6).

Captures what the lab does today, offline, so every later phase can prove it changed nothing:
every suite's per-trial verdicts, grader results, skills and tool-error flags; the traffic -> import
-> accept -> trace-grading loop (exercises the trace-reading conventions); and the shape of key API
responses. Runs in its own process so settings, registries and caches are fresh for the given layout.

    uv run python tests/golden/capture.py --evals <evals dir> --out <file.json>
    uv run python tests/golden/capture.py --update      # rewrite tests/golden/baseline.json from the repo

``--evals`` is used in place (copy it first); ``--update`` copies the committed content of ``evals/``
(no candidates, cassettes or generated dataset folders) to a temp dir.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
BASELINE = HERE / "baseline.json"
# git-ignored, machine-local content: never part of the baseline
LOCAL_ONLY = ("candidates", "cassettes", "synthetic", "traces", "accepted", "langsmith")


def _local_only(directory: str, names: list[str]) -> set[str]:
    # review queues and cassettes anywhere; generated dataset groups only inside datasets/
    parent = Path(directory).name
    return {n for n in names if n in ("candidates", "cassettes") or (parent == "datasets" and n in LOCAL_ONLY)}


def committed_copy(dst: Path) -> Path:
    shutil.copytree(REPO / "evals", dst, ignore=_local_only)
    return dst


def _isolate(evals: Path, work: Path) -> None:
    os.environ.update({
        "EVAL_HARNESS_NO_DOTENV": "1", "LLM_PROVIDER": "fake", "EVALS_DIR": str(evals),
        "DATA_DIR": str(work / "data"), "DATABASE_URL": f"sqlite:///{(work / 'golden.db').as_posix()}",
        "LANGSMITH_TRACING": "false", "LANGCHAIN_TRACING_V2": "false", "LANGSMITH_API_KEY": "",
    })
    for var in ("JUDGE_MODEL", "JUDGE_PROVIDER", "AGENT_MODEL", "OPENROUTER_API_KEY", "GOOGLE_API_KEY",
                "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "TAVILY_API_KEY", "LANGCHAIN_API_KEY", "SIMULATOR_MODEL",
                "SIMULATOR_PROVIDER", "OPENROUTER_MODEL", "OPENROUTER_BASE_URL", "EVAL_PROFILE"):
        os.environ.pop(var, None)


def _calls(pairs: list[list[Any]]) -> list[list[Any]]:
    # parallel tool calls finish in any order (existing behaviour), so lists are compared as multisets;
    # ordering-sensitive checks are still covered by the trajectory graders' verdicts below
    return sorted(pairs)


def _trial_view(t: Any) -> dict[str, Any]:
    return {
        "passed": t.passed, "status": t.outcome.status,
        "skills_loaded": sorted(t.transcript.skills_loaded),
        "tools": _calls([[c.name, c.error] for c in t.transcript.tool_calls]),
        "grades": [[g.grader, g.passed, g.skipped, g.score, g.rationale] for g in t.grades],
    }


def _summary_view(s: dict[str, Any]) -> dict[str, Any]:
    pr = s.get("pass_rates", {})
    return {k: pr.get(k) for k in ("trial_pass_rate", "mean_pass_at_k", "mean_pass_pow_k", "n_tasks", "n_trials", "k")}


def _run_suite(name: str, **overrides: Any) -> dict[str, Any]:
    from eval_harness.evals.runner.service import prepare_runner
    from eval_harness.storage.repositories import trials

    try:
        runner = prepare_runner(name, hooks=[], overrides=overrides)
    except (ValueError, FileNotFoundError, KeyError) as e:
        return {"error": f"{type(e).__name__}: {e}"}
    exp = asyncio.run(runner.run())
    rows = sorted(trials.for_experiment(exp.id), key=lambda t: (t.task_id, t.index))
    return {"status": exp.status, "summary": _summary_view(exp.summary),
            "trials": {f"{t.task_id}#{t.index}": _trial_view(t) for t in rows}}


def _trace_loop() -> dict[str, Any]:
    """Traffic with faults -> JSONL import -> accept -> grade logged transcripts (no re-run)."""
    from eval_harness.evals.data_sources import review
    from eval_harness.evals.data_sources.traces.importer import import_traces
    from eval_harness.evals.data_sources.traffic.simulator import simulate_traffic

    asyncio.run(simulate_traffic(n=16, fault_rate=1.0))
    imp = import_traces("jsonl", limit=16)
    cands = review.list_candidates()
    by_text = {c.user_text: c for c in cands}  # ids derive from random run ids: key by input
    view = {txt: {"tags": sorted(c.tags), "skills_loaded": sorted(c.metadata["transcript"]["skills_loaded"]),
                  "tools": _calls([[x["name"], x["error"]] for x in c.metadata["transcript"]["tool_calls"]])}
            for txt, c in sorted(by_text.items())}
    review.accept(["all"], group="golden_traces")
    run = _run_suite("traces", datasets=["golden_traces"])
    run["trials"] = dict(sorted(  # re-key trials by input text as well
        ((by_text_key(run_key, cands), v) for run_key, v in run.get("trials", {}).items())))
    return {"import": {k: imp[k] for k in ("fetched", "queued", "duplicates_dropped")}, "candidates": view, "run": run}


def by_text_key(run_key: str, cands: list[Any]) -> str:
    task_id, _, idx = run_key.partition("#")
    text = next((c.user_text for c in cands if c.id == task_id), task_id)
    return f"{text}#{idx}"


def _api_shapes() -> dict[str, Any]:
    from fastapi.testclient import TestClient

    from eval_harness.api.main import app

    with TestClient(app) as c:
        cat = c.get("/api/catalog").json()
        exps = c.get("/api/experiments").json()
        smoke = c.get("/api/suites/smoke").json()
        return {
            "catalog_keys": sorted(cat),
            "catalog_suites": sorted((s["name"], s["agent"], s["target"], tuple(s["datasets"])) for s in cat["suites"]),
            "catalog_agents": sorted(a["name"] for a in cat["agents"]),
            "catalog_suite_keys": sorted(cat["suites"][0]),
            "catalog_tools": sorted(t["name"] for t in cat["tools"]),
            "catalog_skills": sorted(s["name"] for s in cat["skills"]),
            "catalog_graders": sorted(g["type"] for g in cat["graders"]),
            "catalog_targets": cat["targets"],
            "experiment_list_keys": sorted(exps[0]) if exps else [],
            "suite_keys": sorted(smoke), "smoke_n_tasks": smoke["n_tasks"],
            "dataset_files": sorted(c.get("/api/datasets/files").json()),
            "faults": c.get("/api/faults").json(),
            "synthesis_configs": c.get("/api/synthesis/configs").json(),
            "candidate_keys": sorted(c.get("/api/candidates").json()[0]) if c.get("/api/candidates").json() else [],
        }


def capture(evals: Path, work: Path) -> dict[str, Any]:
    _isolate(evals, work)
    for root in [evals, *(p.parent for p in (evals / "profiles").glob("*/profile.yaml"))]:  # legacy + profiles
        (root / "candidates").mkdir(exist_ok=True)
        (root / "cassettes").mkdir(exist_ok=True)
    from eval_harness.evals.datasets.loader import list_suites

    suites = {s.name: _run_suite(s.name) for s in list_suites()}
    trace_loop = _trace_loop()
    return {"suites": suites, "trace_loop": trace_loop, "api": _api_shapes()}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--evals", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--update", action="store_true", help="rewrite baseline.json from the repo's evals/")
    a = ap.parse_args()
    work = Path(tempfile.mkdtemp(prefix="evalh-golden-"))
    if a.update:
        evals, out = committed_copy(work / "evals"), BASELINE
    elif a.evals and a.out:
        evals, out = a.evals, a.out
    else:
        ap.error("give --evals and --out, or --update")
    result = capture(evals.resolve(), work)
    out.write_text(json.dumps(result, indent=1, sort_keys=True, default=str), encoding="utf-8")
    print(f"wrote {out} ({sum(len(s.get('trials', {})) for s in result['suites'].values())} suite trials)")


if __name__ == "__main__":
    sys.exit(main())

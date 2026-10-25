"""No-regression gate for the agent-profiles decoupling (.agents/AGENT_PROFILES_PLAN.md, section 6).

Re-captures the offline behaviour in a fresh process and compares it with ``baseline.json``:
suite results and the trace loop must match exactly; API responses may only grow (nothing removed).
Regenerate the baseline only for an intended behaviour change: ``uv run python tests/golden/capture.py --update``.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import capture  # noqa: E402


def run_capture(evals: Path, out: Path) -> dict[str, Any]:
    proc = subprocess.run([sys.executable, str(HERE / "capture.py"), "--evals", str(evals), "--out", str(out)],
                          capture_output=True, text=True, timeout=600)
    assert proc.returncode == 0, proc.stdout[-2000:] + proc.stderr[-4000:]
    return json.loads(out.read_text(encoding="utf-8"))


def api_only_grew(base: Any, cur: Any, path: str = "api") -> list[str]:
    if isinstance(base, dict):
        missing = [f"{path}.{k} missing" for k in base if k not in cur]
        return missing + [m for k in base if k in cur for m in api_only_grew(base[k], cur[k], f"{path}.{k}")]
    if isinstance(base, list) and isinstance(cur, list):
        have = {json.dumps(x, sort_keys=True) for x in cur}
        return [f"{path}: lost {x}" for x in base if json.dumps(x, sort_keys=True) not in have]
    return [] if base == cur else [f"{path}: {base!r} -> {cur!r}"]


def diff(base: Any, cur: Any, path: str = "") -> list[str]:
    if isinstance(base, dict) and isinstance(cur, dict):
        out = [f"{path}/{k}: missing" for k in base if k not in cur] + [f"{path}/{k}: new" for k in cur if k not in base]
        return out + [d for k in base if k in cur for d in diff(base[k], cur[k], f"{path}/{k}")]
    return [] if base == cur else [f"{path}: {json.dumps(base)[:200]} -> {json.dumps(cur)[:200]}"]


def assert_matches_baseline(cur: dict[str, Any]) -> None:
    base = json.loads(capture.BASELINE.read_text(encoding="utf-8"))
    problems = diff(base["suites"], cur["suites"], "suites") + diff(base["trace_loop"], cur["trace_loop"], "trace_loop")
    problems += api_only_grew(base["api"], cur["api"])
    assert not problems, "behaviour changed vs golden baseline:\n" + "\n".join(problems[:40])


@pytest.mark.golden
def test_legacy_layout_matches_golden_baseline(tmp_path):
    evals = capture.committed_copy(tmp_path / "evals")
    assert_matches_baseline(run_capture(evals, tmp_path / "out.json"))


def _migrate(evals: Path) -> None:
    code = ("import sys; from pathlib import Path; from eval_harness.profiles import migrate; "
            "p = migrate.apply(Path(sys.argv[1])); assert not p.note, p.note")
    proc = subprocess.run([sys.executable, "-c", code, str(evals)], capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr[-3000:]


@pytest.mark.golden
def test_migrated_layout_matches_golden_baseline(tmp_path):
    """After `evalh migrate-profiles --apply` every suite, grade and trace-loop result is identical.
    API *values* that are names (agent configs are now variants 'baseline'...) are checked in unit tests;
    here the API may only grow except for the agent list, which is renamed by design (old names = aliases)."""
    evals = capture.committed_copy(tmp_path / "evals")
    _migrate(evals)
    cur = run_capture(evals, tmp_path / "out.json")
    base = json.loads(capture.BASELINE.read_text(encoding="utf-8"))
    assert not diff(base["suites"], cur["suites"], "suites")
    assert not diff(base["trace_loop"], cur["trace_loop"], "trace_loop")
    api_base = {k: v for k, v in base["api"].items() if k != "catalog_agents"}  # suites keep the old names
    assert not api_only_grew(api_base, cur["api"])
    assert sorted(cur["api"]["catalog_agents"]) == ["baseline", "generic-loader", "no-skills"]


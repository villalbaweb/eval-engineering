"""`evalh scaffold <kind> <name>`: create a new plug-in component plus a unit test."""

from __future__ import annotations

import re
from pathlib import Path

from eval_harness.core.settings import REPO_ROOT

PKG = Path(__file__).resolve().parents[1]
TESTS = REPO_ROOT / "backend" / "tests" / "unit"

GRADER = '''from __future__ import annotations

from eval_harness.evals.domain.grade import GradeResult
from eval_harness.evals.graders.base import GradeContext, Grader, register_grader


@register_grader("__NAME__")
class __CLASS__(Grader):
    """TODO: one sentence on what this grader checks."""

    layer = 1  # 1 code (cheap) | 2 trajectory | 3 model (expensive)
    description = "TODO"

    def grade(self, ctx: GradeContext) -> GradeResult:
        # read what you need: ctx.task.expected, ctx.transcript (messages, tool_calls, skills_loaded), ctx.outcome
        if not ctx.task.expected.answer_contains:
            return self.skip("nothing to check for this task")
        ok = bool(ctx.transcript.final_answer)
        return self.passed(ok, "answer present" if ok else "empty answer")
'''
GRADER_TEST = '''from eval_harness.evals.domain.outcome import Outcome
from eval_harness.evals.domain.task import Task
from eval_harness.evals.domain.transcript import Transcript
from eval_harness.evals.graders.base import GradeContext, grader_registry


def test___NAME___grader():
    cls = grader_registry.get("__NAME__")
    task = Task(id="t", input={"messages": [{"role": "user", "content": "hi"}]}, expected={"answer_contains": ["x"]})
    t = Transcript(messages=[{"role": "assistant", "content": "x"}])
    res = cls(name="__NAME__").grade(GradeContext(task, t, Outcome()))
    assert res.passed is True
'''
TOOL = '''from __future__ import annotations

from langchain_core.tools import tool

from eval_harness.tools.base import register_tool


@register_tool(side_effects=False, replayable=True, cost_hint="low", tags=())
@tool
def __NAME__(query: str) -> str:
    """TODO: what the tool does and when the agent should call it. Return errors as text starting with 'ERROR'."""
    return f"__NAME__ result for {query}"
'''
TOOL_TEST = '''from eval_harness.tools.base import tool_registry


def test___NAME___tool():
    assert "__NAME__" in tool_registry
    assert "result" in tool_registry.get("__NAME__").invoke({"query": "x"})
'''
METRIC = '''from __future__ import annotations

from typing import Any

from eval_harness.evals.domain.task import Task
from eval_harness.evals.domain.trial import Trial
from eval_harness.evals.metrics.registry import metric_registry


@metric_registry.register("__NAME__")
def __NAME__(trials: list[Trial], tasks: dict[str, Task], k: int) -> dict[str, Any]:
    return {"n_trials": len(trials)}
'''
METRIC_TEST = '''from eval_harness.evals.metrics.registry import metric_registry


def test___NAME___metric():
    assert metric_registry.get("__NAME__")([], {}, 1) == {"n_trials": 0}
'''
TARGET = '''from __future__ import annotations

from eval_harness.evals.domain.outcome import Outcome
from eval_harness.evals.domain.suite import RunSettings
from eval_harness.evals.domain.task import Task
from eval_harness.evals.domain.transcript import Transcript
from eval_harness.evals.targets.base import Target, TrialInfo, register_target


@register_target("__NAME__")
class __CLASS__(Target):
    """Evaluate anything that can turn a task into a transcript (another agent, an HTTP service...)."""

    async def run(self, task: Task, run: RunSettings, info: TrialInfo) -> tuple[Transcript, Outcome]:
        answer = "TODO call your system with task.input['messages'] and map the response"
        t = Transcript(messages=[*task.input["messages"], {"role": "assistant", "content": answer}])
        return t, Outcome(final_answer=answer)
'''
TARGET_TEST = '''import asyncio

from eval_harness.evals.domain.suite import RunSettings
from eval_harness.evals.domain.task import Task
from eval_harness.evals.targets.base import TrialInfo, target_registry


def test___NAME___target():
    t = target_registry.get("__NAME__")()
    task = Task(id="t", input={"messages": [{"role": "user", "content": "hi"}]})
    tr, out = asyncio.run(t.run(task, RunSettings(), TrialInfo("e", "t", 0, "s")))
    assert out.status == "ok" and tr.final_answer
'''
GENERATOR = '''from __future__ import annotations

from eval_harness.evals.data_sources.synthesis.base import Generator, register_generator
from eval_harness.evals.domain.task import Task


@register_generator("__NAME__")
class __CLASS__(Generator):
    description = "TODO"

    def generate(self) -> list[Task]:
        return [self.make_task(i, f"example input {i}", {}) for i in range(self.cfg.count)]
'''
GENERATOR_TEST = '''from eval_harness.evals.data_sources.synthesis.base import SynthesisConfig, generator_registry


def test___NAME___generator():
    cfg = SynthesisConfig(name="t", generator="__NAME__", count=3)
    assert len(generator_registry.get("__NAME__")(cfg).generate()) == 3
'''
SKILL = '''---
name: __DASH__
description: TODO one sentence - what the skill teaches and when to load it.
version: "1"
---

# __DASH__

Step-by-step instructions the agent follows once this skill is loaded.
'''


def _cls(name: str) -> str:
    return "".join(p.capitalize() for p in re.split(r"[_\-]", name))


def scaffold(kind: str, name: str) -> list[Path]:
    snake, dash = name.replace("-", "_"), name.replace("_", "-")
    fill = lambda s: s.replace("__NAME__", snake).replace("__CLASS__", _cls(snake)).replace("__DASH__", dash)  # noqa: E731
    plans: dict[str, list[tuple[Path, str]]] = {
        "grader": [(PKG / "evals/graders/code" / f"{snake}.py", GRADER), (TESTS / f"test_{snake}_grader.py", GRADER_TEST)],
        "tool": [(PKG / "tools" / f"{snake}.py", TOOL), (TESTS / f"test_{snake}_tool.py", TOOL_TEST)],
        "metric": [(PKG / "evals/metrics" / f"{snake}.py", METRIC), (TESTS / f"test_{snake}_metric.py", METRIC_TEST)],
        "target": [(PKG / "evals/targets" / f"{snake}.py", TARGET), (TESTS / f"test_{snake}_target.py", TARGET_TEST)],
        "generator": [(PKG / "evals/data_sources/synthesis" / f"{snake}.py", GENERATOR),
                      (TESTS / f"test_{snake}_generator.py", GENERATOR_TEST)],
        "skill": [(PKG / "skills/library" / dash / "SKILL.md", SKILL)],
    }
    if kind not in plans:
        raise ValueError(f"kind must be one of {sorted(plans)}")
    created = []
    for path, tpl in plans[kind]:
        if path.exists():
            raise FileExistsError(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(fill(tpl), encoding="utf-8")
        created.append(path)
    return created

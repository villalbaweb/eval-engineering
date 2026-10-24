"""The experiment mirror must scope feedback to its project/trace (LangSmith deprecates unscoped feedback)."""

from types import SimpleNamespace
from uuid import uuid4

from eval_harness.evals.domain.experiment import Experiment
from eval_harness.evals.domain.grade import GradeResult
from eval_harness.evals.domain.task import Task
from eval_harness.evals.domain.trial import Trial
from eval_harness.integrations.langsmith import mirror as mirror_mod


class StubClient:
    def __init__(self):
        self.runs, self.feedback = [], []
        self.project = SimpleNamespace(id=uuid4(), url="https://smith.example/p/1")

    def create_project(self, **kw):
        return self.project

    def create_run(self, **kw):
        self.runs.append(kw)

    def update_run(self, *a, **kw):
        pass

    def create_feedback(self, run_id, key, **kw):
        self.feedback.append({"run_id": run_id, "key": key, **kw})


def test_feedback_is_scoped_to_session_and_trace(monkeypatch):
    stub = StubClient()
    monkeypatch.setattr(mirror_mod, "enabled", lambda: True)
    monkeypatch.setattr(mirror_mod, "get_client", lambda: stub)
    monkeypatch.setattr(mirror_mod.datasets, "push_tasks", lambda *a, **k: {"dataset_id": "d", "example_ids": {"t1": "e1"}})

    task = Task(id="t1", input={"messages": [{"role": "user", "content": "hi"}]})
    trial = Trial(id="tr1", experiment_id="e", task_id="t1", index=0,
                  grades=[GradeResult.of("skill_selection", True, "ok")])
    exp = Experiment(id="e", name="exp-1", suite="smoke")
    mirror_mod.ExperimentMirror().on_experiment_end(exp, [trial], {"t1": task})

    assert len(stub.runs) == 1 and exp.langsmith_url == "https://smith.example/p/1"
    assert {f["key"] for f in stub.feedback} == {"skill_selection", "trial_passed"}
    for f in stub.feedback:
        assert f["session_id"] == stub.project.id and f["trace_id"] == f["run_id"]

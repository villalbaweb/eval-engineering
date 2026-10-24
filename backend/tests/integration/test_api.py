import json
import time

import pytest
from fastapi.testclient import TestClient

from eval_harness.api.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def wait_done(client, exp_id, timeout=60):
    t0 = time.time()
    while time.time() - t0 < timeout:
        e = client.get(f"/api/experiments/{exp_id}").json()
        if e["status"] in ("completed", "failed", "cancelled"):
            return e
        time.sleep(0.2)
    raise AssertionError("experiment did not finish")


def test_health_and_catalog(client):
    assert client.get("/health").json()["status"] == "ok"
    c = client.get("/api/catalog").json()
    assert len(c["tools"]) >= 5 and len(c["skills"]) >= 5 and c["suites"] and c["graders"]
    assert c["models"]["agent"]["provider"] == "fake" and c["langsmith"]["enabled"] is False
    assert any(s["tool"].startswith("load_skill_") for s in c["skills"])


def test_launch_experiment_stream_events_and_inspect_trials(client):
    r = client.post("/api/experiments", json={"suite": "smoke", "max_tasks": 3})
    assert r.status_code == 200, r.text
    exp_id = r.json()["id"]
    e = wait_done(client, exp_id)
    assert e["status"] == "completed" and e["summary"]["pass_rates"]["n_trials"] == 3
    # events are replayed for late subscribers and terminate
    with client.stream("GET", f"/api/experiments/{exp_id}/events") as s:
        types = [ln.split(":", 1)[1].strip() for ln in s.iter_lines() if ln.startswith("event:")]
    assert types[0] == "experiment_started" and types[-1] == "experiment_done"
    trials = client.get(f"/api/experiments/{exp_id}/trials").json()
    assert len(trials) == 3 and trials[0]["grades"]
    detail = client.get(f"/api/trials/{trials[0]['id']}").json()
    assert detail["task"]["id"] == trials[0]["task_id"] and detail["trial"]["transcript"]["messages"]
    assert exp_id in [x["id"] for x in client.get("/api/experiments").json()]


def test_annotation_queue_and_calibration(client):
    exp_id = client.post("/api/experiments", json={"suite": "skill-selection", "max_tasks": 4, "k": 1}).json()["id"]
    wait_done(client, exp_id)
    q = client.get("/api/annotations/queue", params={"experiment_id": exp_id}).json()
    assert len(q) == 4
    for i, item in enumerate(q):
        assert client.post("/api/annotations", json={"trial_id": item["trial_id"], "good": i % 2 == 0,
                                                     "failure_tags": [] if i % 2 == 0 else ["x"]}).status_code == 200
    assert client.get("/api/annotations/queue", params={"experiment_id": exp_id}).json() == []
    cal = client.get("/api/calibration", params={"experiment_id": exp_id}).json()
    assert cal["n_labeled"] == 4 and "skill_selection" in cal["graders"]


def test_regrade_and_compare_endpoints(client):
    a = client.post("/api/experiments", json={"suite": "skill-selection", "max_tasks": 3}).json()["id"]
    wait_done(client, a)
    b = client.post(f"/api/experiments/{a}/regrade", json={"graders": [{"type": "step_efficiency"}]}).json()["id"]
    assert wait_done(client, b)["status"] == "completed"
    cmp = client.get("/api/compare", params={"a": a, "b": b}).json()
    assert cmp["a"]["id"] == a and "per_task" in cmp
    assert client.get("/api/compare", params={"a": a, "b": "nope"}).status_code == 404


def test_launch_validation_errors(client):
    assert client.post("/api/experiments", json={"suite": "does-not-exist"}).status_code == 400
    assert client.post("/api/experiments", json={"suite": "smoke", "agent": "nope"}).status_code in (400, 200)


def test_chat_stream_shows_skill_load_and_tool_events(client):
    body = {"messages": [{"role": "user", "content": "Help me write an LLM-judge rubric for conciseness."}]}
    events = []
    with client.stream("POST", "/api/chat/stream", json=body) as s:
        cur = None
        for ln in s.iter_lines():
            if ln.startswith("event:"):
                cur = ln.split(":", 1)[1].strip()
            elif ln.startswith("data:") and cur:
                events.append((cur, json.loads(ln.split(":", 1)[1])))
    kinds = [k for k, _ in events]
    assert kinds[0] == "start" and "skill_loaded" in kinds and "tool_start" in kinds and "done" in kinds
    done = next(d for k, d in events if k == "done")
    assert done["skills_loaded"] == ["rubric-authoring"] and done["answer"]
    assert client.post("/api/chat/feedback", json={"run_id": done["run_id"], "thumbs": 1}).json()["ok"]


def test_dataset_editor_validates_before_saving(client):
    files = client.get("/api/datasets/files").json()
    assert "tool-use/basic.yaml" in files
    ok = "tasks:\n  - id: api-t1\n    input: { messages: [{role: user, content: hi}] }\n"
    assert client.put("/api/datasets/files/api/new.yaml", json={"content": ok}).json()["tasks"] == 1
    assert client.put("/api/datasets/files/api/bad.yaml", json={"content": "tasks:\n  - id: x\n"}).status_code == 422
    assert client.get("/api/datasets/files/../../secrets.yaml").status_code in (400, 404)


def test_synthesis_candidates_and_accept(client):
    assert "skill-queries" in client.get("/api/synthesis/configs").json()
    res = client.post("/api/synthesis/run", json={"config": "adversarial"}).json()
    assert res["queued"] > 0
    ids = [c["id"] for c in client.get("/api/candidates").json()]
    assert ids
    assert client.post("/api/candidates/accept", json={"ids": ids[:1], "group": "api_accepted"}).json()["accepted"] == 1
    assert client.post("/api/candidates/reject", json={"ids": ids[1:]}).json()["rejected"] == len(ids) - 1
    assert client.post("/api/synthesis/run", json={"config": "missing"}).status_code == 400


def test_traffic_then_import_then_candidates(client):
    t = client.post("/api/traffic/simulate", json={"n": 6, "fault_rate": 0.5}).json()
    assert t["sessions"] == 6
    imp = client.post("/api/traces/import", json={"adapter": "jsonl", "limit": 6}).json()
    assert imp["fetched"] == 6
    assert any(c["has_transcript"] for c in client.get("/api/candidates").json()) or imp["queued"] == 0

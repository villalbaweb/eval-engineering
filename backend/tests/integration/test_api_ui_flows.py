"""The UI flows that close the loop: edit a candidate, accept it into any group, run that group,
and author suites - all through the API the frontend uses."""

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


def test_edit_candidate_accept_and_run_the_group(client):
    client.post("/api/traffic/simulate", json={"n": 3, "fault_rate": 0.0})
    client.post("/api/traces/import", json={"adapter": "jsonl", "limit": 3})
    cands = [c for c in client.get("/api/candidates").json() if c["has_transcript"]]
    assert cands
    cid = cands[0]["id"]

    y = client.get(f"/api/candidates/{cid}/yaml").json()["content"]
    assert "transcript" not in y  # hidden from the editor ...
    edited = y + "expected:\n  answer_contains: [x]\n"
    assert client.put(f"/api/candidates/{cid}/yaml", json={"content": edited}).status_code == 200
    after = next(c for c in client.get("/api/candidates").json() if c["id"] == cid)
    assert after["expected"]["answer_contains"] == ["x"] and after["has_transcript"]  # ... but kept
    assert client.put(f"/api/candidates/{cid}/yaml", json={"content": "id: other\n"}).status_code == 422
    assert client.put(f"/api/candidates/{cid}/yaml", json={"content": "- not a mapping\n"}).status_code == 422

    assert client.post("/api/candidates/accept", json={"ids": [cid], "group": "ui_flow"}).json()["accepted"] == 1
    # no suite lists 'ui_flow': run it with the traces suite as the template (graders + trace target)
    r = client.post("/api/experiments", json={"suite": "traces", "datasets": ["ui_flow"]})
    assert r.status_code == 200, r.text
    e = wait_done(client, r.json()["id"])
    assert e["status"] == "completed" and e["summary"]["pass_rates"]["n_tasks"] == 1
    assert e["snapshot"]["suite"]["datasets"] == ["ui_flow"]  # recorded, so compare can flag it
    bad = client.post("/api/experiments", json={"suite": "traces", "datasets": ["no-such-group"]})
    assert bad.status_code == 400 and "no-such-group" in bad.json()["detail"]


def test_suite_editor_validates_before_saving(client):
    src = client.get("/api/suites/smoke").json()
    assert src["n_tasks"] > 0
    ok = src["yaml"].replace("name: smoke", "name: ui-suite")
    res = client.put("/api/suites/ui-suite", json={"content": ok}).json()
    assert res["saved"] == "ui-suite" and res["n_tasks"] == src["n_tasks"]
    assert "ui-suite" in [s["name"] for s in client.get("/api/catalog").json()["suites"]]

    def status(name, content):
        return client.put(f"/api/suites/{name}", json={"content": content}).status_code

    assert status("other-name", ok) == 422  # name must match the file
    assert status("ui-suite", ok.replace("type: ", "type: nope_", 1)) == 422  # unknown grader
    assert status("ui-suite", "name: ui-suite\n") == 422  # missing datasets/graders
    assert status("Bad Name", ok) in (400, 404, 422)
    empty = ok.replace("datasets:", "datasets: [nothing-here]\n_old_datasets:", 1)
    assert client.put("/api/suites/ui-suite", json={"content": empty}).json()["warning"]


def test_fault_profiles_are_listed(client):
    assert "kb_down" in client.get("/api/faults").json()

"""P6: the committed second agent (evals/profiles/demo-external) is evaluated end to end through the
API with no engine code knowing about it - only files in its folder. Dress rehearsal for a real agent."""

import time

import pytest
from fastapi.testclient import TestClient

from eval_harness.api.main import app

H = {"X-Eval-Profile": "demo-external"}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def wait(c, exp_id):
    for _ in range(300):
        e = c.get(f"/api/experiments/{exp_id}", headers=H).json()
        if e["status"] in ("completed", "failed", "cancelled"):
            return e
        time.sleep(0.1)
    raise AssertionError("not finished")


def grades(c, exp_id):
    return {t["task_id"]: {g["grader"]: g for g in t["grades"]} for t in c.get(f"/api/experiments/{exp_id}/trials", headers=H).json()}


def test_it_is_listed_next_to_the_copilot(client):
    names = [p["name"] for p in client.get("/api/profiles").json()["profiles"]]
    assert {"copilot", "demo-external"} <= set(names)
    cat = client.get("/api/catalog", headers=H).json()
    assert cat["profile"]["variants"][0]["target"] == "trace_source"
    assert [s["name"] for s in cat["suites"]] == ["traces"] and cat["datasets"] == {"logged": 2}
    assert "refunds" in [s["name"] for s in cat["profile"]["inventory"]["skills"]]


def test_curated_logs_are_graded_with_its_conventions(client):
    exp = wait(client, client.post("/api/experiments", json={"suite": "traces"}, headers=H).json()["id"])
    assert exp["status"] == "completed" and exp["snapshot"]["mode"] == "trace"
    g = grades(client, exp["id"])
    assert g["support-refund-01"]["skill_selection"]["passed"]  # use_capability(name=refunds)
    assert g["support-refund-01"]["tool_errors"]["passed"]
    assert not g["support-tracking-01"]["tool_errors"]["passed"]  # "HTTP 503 ..." is an error for this agent
    assert g["support-refund-01"]["citation_grounding"]["skipped"]  # no citation format


def test_import_review_accept_run_compare(client):
    imp = client.post("/api/traces/import", json={"limit": 10}, headers=H).json()  # adapter + path from profile
    assert imp["fetched"] == 3
    cands = {c["input"]["messages"][0]["content"]: c for c in client.get("/api/candidates", headers=H).json()}
    refund = cands["Refund order 2210 please"]
    assert refund["thumbs"] == 0 and "negative-feedback" in refund["tags"]

    y = client.get(f"/api/candidates/{refund['id']}/yaml", headers=H).json()["content"]
    saved = client.put(f"/api/candidates/{refund['id']}/yaml", headers=H,
                       json={"content": y + "expected:\n  skills_loaded: [refunds]\n  answer_not_contains: [done]\n"}).json()
    assert saved["warnings"] == []  # names match its inventory
    acc = client.post("/api/candidates/accept", json={"ids": [c["id"] for c in cands.values()], "group": "logged"},
                      headers=H).json()
    assert acc["accepted"] == 3

    exp = wait(client, client.post("/api/experiments", json={"suite": "traces"}, headers=H).json()["id"])
    g = grades(client, exp["id"])
    rid = refund["id"]
    assert g[rid]["skill_selection"]["passed"] and not g[rid]["tool_errors"]["passed"]  # {"error": ...}
    assert exp["summary"]["pass_rates"]["n_tasks"] == 5

    first = client.get("/api/experiments", headers=H).json()[-1]["id"]
    cmp = client.get("/api/compare", params={"a": first, "b": exp["id"]}, headers=H).json()
    assert not any(w.startswith("different agents") for w in cmp["warnings"])


def test_what_it_cannot_do_is_refused_with_a_reason(client):
    assert "cannot chat" in client.post("/api/chat/stream", headers=H,
                                        json={"messages": [{"role": "user", "content": "hi"}]}).json()["detail"]
    assert client.post("/api/traffic/simulate", json={"n": 1}, headers=H).status_code == 400
    r = client.post("/api/experiments", json={"suite": "traces", "mode": "live"}, headers=H)
    assert r.status_code == 400 and "use mode 'trace'" in r.json()["detail"]

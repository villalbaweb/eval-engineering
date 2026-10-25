"""P4: the API follows the request's agent profile; old requests (no profile) behave as before."""

import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from eval_harness.api.main import app  # noqa: E402
from profile_fixtures import make_demo_profile, private_evals  # noqa: E402

DEMO = {"X-Eval-Profile": "demo"}


@pytest.fixture()
def client(tmp_path, tmp_evals):
    with private_evals(tmp_evals, tmp_path / "evals") as d, TestClient(app) as c:
        make_demo_profile(d)
        yield c


def wait(c, exp_id, headers=None):
    for _ in range(300):
        e = c.get(f"/api/experiments/{exp_id}", headers=headers).json()
        if e["status"] in ("completed", "failed", "cancelled"):
            return e
        time.sleep(0.1)
    raise AssertionError("not finished")


def test_profiles_endpoint_and_selection(client):
    p = client.get("/api/profiles").json()
    assert p["active"] == "copilot" and {"copilot", "demo"} <= {x["name"] for x in p["profiles"]}
    demo = next(x for x in p["profiles"] if x["name"] == "demo")
    assert demo["variants"][0] == {"name": "prod-traces", "description": "read-only production logs",
                                   "target": "trace_source", "aliases": [], "capabilities": [],
                                   "capabilities_declared": True}
    copilot = next(x for x in p["profiles"] if x["name"] == "copilot")
    assert "chat" in copilot["variants"][0]["capabilities"] and copilot["legacy_layout"]
    assert client.get("/api/profiles", headers=DEMO).json()["active"] == "demo"
    assert client.get("/api/profiles?profile=demo").json()["active"] == "demo"
    r = client.get("/api/catalog", headers={"X-Eval-Profile": "nope"})
    assert r.status_code == 400 and "not found" in r.json()["detail"]


def test_catalog_suites_and_datasets_follow_the_profile(client):
    cop = client.get("/api/catalog").json()
    assert "smoke" in [s["name"] for s in cop["suites"]] and cop["profile"]["inventory"]["from_registry"]
    assert "knowledge_base_search" in [t["name"] for t in cop["profile"]["inventory"]["tools"]]
    demo = client.get("/api/catalog", headers=DEMO).json()
    assert [s["name"] for s in demo["suites"]] == ["traces"] and demo["datasets"] == {"logged": 2}
    assert [t["name"] for t in demo["profile"]["inventory"]["tools"]] == ["search_orders"]
    assert demo["profile"]["conventions"]["citations"] is None
    assert client.get("/api/suites/smoke", headers=DEMO).status_code == 404  # not this agent's suite


def test_features_a_variant_cannot_support_are_refused_with_a_reason(client):
    body = {"messages": [{"role": "user", "content": "hi"}]}
    r = client.post("/api/chat/stream", json=body, headers=DEMO)
    assert r.status_code == 400 and "cannot chat" in r.json()["detail"]
    r = client.post("/api/traffic/simulate", json={"n": 1}, headers=DEMO)
    assert r.status_code == 400 and "simulated traffic" in r.json()["detail"]
    r = client.post("/api/experiments", json={"suite": "traces", "mode": "live"}, headers=DEMO)
    assert r.status_code == 400 and "cannot be run from the lab" in r.json()["detail"]


def test_runs_and_history_are_per_profile(client):
    a = client.post("/api/experiments", json={"suite": "smoke", "max_tasks": 1}).json()["id"]
    b = client.post("/api/experiments", json={"suite": "traces"}, headers=DEMO).json()["id"]
    assert wait(client, a)["snapshot"]["profile"] == "copilot"
    eb = wait(client, b, DEMO)
    assert eb["status"] == "completed" and eb["snapshot"]["profile"] == "demo"
    cop_ids = [e["id"] for e in client.get("/api/experiments").json()]
    demo_ids = [e["id"] for e in client.get("/api/experiments", headers=DEMO).json()]
    assert a in cop_ids and b not in cop_ids and demo_ids == [b]
    every = client.get("/api/experiments?all_profiles=true").json()
    assert {a, b} <= {e["id"] for e in every}
    run_b = next(e for e in every if e["id"] == b)
    assert (run_b["profile"], run_b["variant"], run_b["mode"]) == ("demo", "prod-traces", "trace")


def test_import_and_review_use_the_profile_conventions_and_inventory(client):
    r = client.post("/api/traces/import", json={"limit": 10}, headers=DEMO).json()  # adapter+path from profile
    assert r["fetched"] == 2 and r["queued"] == 2
    cands = client.get("/api/candidates", headers=DEMO).json()
    demo_ids = {c["id"] for c in cands}
    assert demo_ids == {"trace-run0", "trace-run1"}
    assert not demo_ids & {c["id"] for c in client.get("/api/candidates").json()}  # queues are per profile
    cid = cands[0]["id"]
    y = client.get(f"/api/candidates/{cid}/yaml", headers=DEMO).json()["content"]
    res = client.put(f"/api/candidates/{cid}/yaml", headers=DEMO,
                     json={"content": y + "expected:\n  skills_loaded: [refundz]\n  forbidden_tools: [search_orders]\n"})
    assert res.status_code == 200 and res.json()["warnings"] == [f"{cid}: skill 'refundz' is not in the 'demo' inventory"]
    acc = client.post("/api/candidates/accept", json={"ids": [cid], "group": "logged"}, headers=DEMO).json()
    assert acc["accepted"] == 1 and acc["warnings"]
    from eval_harness.core.settings import get_settings
    from eval_harness.profiles import use_profile

    with use_profile("demo"):
        stored = (get_settings().datasets_dir / "logged" / "logged.yaml").read_text(encoding="utf-8")
    assert "refundz" in stored and "use_capability" in stored  # transcript kept, tool calls derived


def test_requests_without_a_profile_are_unchanged(client):
    assert client.post("/api/experiments", json={"suite": "does-not-exist"}).status_code == 400
    smoke = client.get("/api/suites/smoke").json()
    assert smoke["n_tasks"] > 0
    r = client.get("/api/rubrics").json()
    assert "conciseness" in r

"""The REAL ChatOpenRouter client driving the agent loop against a local mock of the OpenRouter HTTP API.

Proves provider wiring (settings -> factory -> ChatOpenRouter -> create_agent -> tool calls -> transcript)
without a key or network. It does not prove anything about real model behaviour.
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from eval_harness.agent.config import load_agent_config
from eval_harness.agent.factory import build_agent
from eval_harness.agent.run_context import RunContext

REQUESTS: list[dict] = []


class Mock(BaseHTTPRequestHandler):
    def log_message(self, *a):  # silence
        pass

    def do_POST(self):  # noqa: N802
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        REQUESTS.append({"path": self.path, "auth": self.headers.get("Authorization"), "body": body})
        has_tool_result = any(m.get("role") == "tool" for m in body["messages"])
        if has_tool_result:
            msg = {"role": "assistant", "content": "Use one binary criterion per judge call."}
            finish = "stop"
        else:
            msg = {"role": "assistant", "content": None, "tool_calls": [
                {"id": "call_1", "type": "function",
                 "function": {"name": "load_skill_rubric_authoring", "arguments": "{}"}}]}
            finish = "tool_calls"
        out = {"id": "gen-1", "object": "chat.completion", "created": 1, "model": body["model"], "system_fingerprint": "fp",
               "choices": [{"index": 0, "message": msg, "finish_reason": finish}],
               "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}
        data = json.dumps(out).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


@pytest.fixture
def mock_openrouter(monkeypatch):
    srv = HTTPServer(("127.0.0.1", 0), Mock)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    REQUESTS.clear()
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test-key")
    monkeypatch.setenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
    monkeypatch.setenv("OPENROUTER_BASE_URL", f"http://127.0.0.1:{srv.server_port}/api/v1")
    yield srv
    srv.shutdown()


def test_agent_loop_runs_through_real_chat_openrouter(mock_openrouter):
    ctx = RunContext()
    agent = build_agent(load_agent_config("copilot-baseline"), ctx=ctx)
    assert agent.model_spec.slug == "openrouter:openai/gpt-4o-mini"
    t = agent.run([{"role": "user", "content": "Help me write a rubric."}])

    assert t.skills_loaded == ["rubric-authoring"]  # the model's tool call executed the skill loader
    assert t.final_answer == "Use one binary criterion per judge call."
    assert t.usage.total_tokens == 30 and t.usage.model_calls == 2
    assert len(REQUESTS) == 2
    first = REQUESTS[0]
    assert first["path"].endswith("/chat/completions") and first["auth"] == "Bearer sk-test-key"
    assert first["body"]["model"] == "openai/gpt-4o-mini"
    names = {t_["function"]["name"] for t_ in first["body"]["tools"]}  # tools + skill loaders were sent to the model
    assert {"knowledge_base_search", "load_skill_rubric_authoring"} <= names
    assert first["body"]["messages"][0]["role"] == "system" and "Available skills" in first["body"]["messages"][0]["content"]

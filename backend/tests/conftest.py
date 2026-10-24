"""Test isolation: offline model, tmp DB/data, and a private copy of the evals/ folder."""

import os
import shutil
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="evalh-tests-"))
_REPO = Path(__file__).resolve().parents[2]
shutil.copytree(_REPO / "evals", _TMP / "evals",
                ignore=shutil.ignore_patterns("candidates", "cassettes", "synthetic", "traces"))
(_TMP / "evals" / "candidates").mkdir()
(_TMP / "evals" / "cassettes").mkdir()

os.environ.update({
    "EVAL_HARNESS_NO_DOTENV": "1",  # never read the developer's real .env (keys!) in tests
    "LLM_PROVIDER": "fake",
    "EVALS_DIR": str(_TMP / "evals"),
    "DATA_DIR": str(_TMP / "data"),
    "DATABASE_URL": f"sqlite:///{(_TMP / 'test.db').as_posix()}",
    "LANGSMITH_TRACING": "false",
    "LANGCHAIN_TRACING_V2": "false",
    "LANGSMITH_API_KEY": "",
})
for var in ("JUDGE_MODEL", "JUDGE_PROVIDER", "AGENT_MODEL", "OPENROUTER_API_KEY", "GOOGLE_API_KEY",
            "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "TAVILY_API_KEY", "LANGCHAIN_API_KEY", "SIMULATOR_MODEL",
            "SIMULATOR_PROVIDER", "OPENROUTER_MODEL", "OPENROUTER_BASE_URL"):
    os.environ.pop(var, None)

import pytest  # noqa: E402


@pytest.fixture(scope="session")
def tmp_evals() -> Path:
    return _TMP / "evals"

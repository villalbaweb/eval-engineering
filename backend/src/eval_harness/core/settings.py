"""Typed application settings (env / .env -> pydantic).

LLM provider settings live in :mod:`eval_harness.llm.settings`; this module covers
paths, storage, LangSmith and tool keys.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[4]

# LangChain / LangSmith read their configuration straight from ``os.environ``,
# so the .env file must be exported to the process environment, not only parsed.
# EVAL_HARNESS_NO_DOTENV=1 makes the process ignore .env entirely (the test suite sets it so a developer's
# real keys can never leak into tests).
USE_DOTENV = not os.environ.get("EVAL_HARNESS_NO_DOTENV")
if USE_DOTENV:
    load_dotenv(REPO_ROOT / ".env", override=False)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(REPO_ROOT / ".env") if USE_DOTENV else None, extra="ignore")

    evals_dir: Path = Field(default=REPO_ROOT / "evals", alias="EVALS_DIR")
    data_dir: Path = Field(default=REPO_ROOT / "data", alias="DATA_DIR")
    database_url: str = Field(default="", alias="DATABASE_URL")

    langsmith_tracing: bool = Field(default=False, alias="LANGSMITH_TRACING")
    langsmith_api_key: str = Field(default="", alias="LANGSMITH_API_KEY")
    langsmith_project: str = Field(default="eval-engineering", alias="LANGSMITH_PROJECT")

    tavily_api_key: str = Field(default="", alias="TAVILY_API_KEY")

    cors_origins: str = Field(default="http://localhost:5173,http://localhost:8080", alias="CORS_ORIGINS")

    @property
    def db_url(self) -> str:
        """Database URL. Relative sqlite paths resolve against the repo root (never the cwd) and
        their folder is created, so ``sqlite:///./data/x.db`` works from any directory."""
        if not self.database_url:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            return f"sqlite:///{(self.data_dir / 'eval_harness.db').as_posix()}"
        prefix = "sqlite:///"
        if self.database_url.startswith(prefix) and ":memory:" not in self.database_url:
            path = Path(self.database_url[len(prefix):])
            if not path.is_absolute():
                path = REPO_ROOT / path
            path.parent.mkdir(parents=True, exist_ok=True)
            return f"{prefix}{path.as_posix()}"
        return self.database_url

    @property
    def langsmith_enabled(self) -> bool:
        return self.langsmith_tracing and bool(self.langsmith_api_key)

    # --- content folders (data, not code) ---
    # Agent-specific content lives in the ACTIVE PROFILE's folder: evals/profiles/<name>/ in the profiles
    # layout, or evals/ itself in the legacy flat layout (so these paths are unchanged there).
    @property
    def profile_dir(self) -> Path:
        from eval_harness.profiles.loader import profile_root

        return profile_root(evals=self.evals_dir)

    @property
    def agents_dir(self) -> Path:
        """Legacy layout only: agent configs (variants live in ``<profile>/variants`` otherwise)."""
        return self.evals_dir / "agents"

    @property
    def datasets_dir(self) -> Path:
        return self.profile_dir / "datasets"

    @property
    def suites_dir(self) -> Path:
        return self.profile_dir / "suites"

    @property
    def rubrics_dir(self) -> Path:
        """The active profile's rubrics (see ``shared_rubrics_dir`` for the fallback)."""
        return self.profile_dir / "rubrics"

    @property
    def shared_rubrics_dir(self) -> Path:
        return self.evals_dir / "rubrics"

    @property
    def cassettes_dir(self) -> Path:
        return self.profile_dir / "cassettes"

    @property
    def corpus_dir(self) -> Path:
        return self.profile_dir / "corpus"

    @property
    def synthesis_dir(self) -> Path:
        return self.profile_dir / "synthesis"

    @property
    def faults_dir(self) -> Path:
        return self.profile_dir / "faults"

    @property
    def candidates_dir(self) -> Path:
        return self.profile_dir / "candidates"


@lru_cache
def get_settings() -> Settings:
    return Settings()


def disable_tracing() -> None:
    """Turn LangSmith tracing off for this process (used by tests / offline runs)."""
    for k in ("LANGSMITH_TRACING", "LANGCHAIN_TRACING_V2"):
        os.environ[k] = "false"

"""Regression: `sqlite:///./data/x.db` copied from .env.example failed with 'unable to open database file'
when the CLI ran from backend/ (the relative path was resolved against the cwd and its folder did not exist)."""

import os
from pathlib import Path

from eval_harness.core.settings import REPO_ROOT, Settings


def test_relative_sqlite_url_resolves_against_repo_root_and_creates_folder(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # cwd must not matter
    rel = f"data_settings_test_{os.getpid()}/nested/app.db"
    s = Settings(DATABASE_URL=f"sqlite:///./{rel}")
    url = s.db_url
    target = REPO_ROOT / rel
    try:
        assert url == f"sqlite:///{target.as_posix()}"
        assert target.parent.is_dir() and not (tmp_path / "data_settings_test").exists()
    finally:
        import shutil

        shutil.rmtree(REPO_ROOT / rel.split("/")[0], ignore_errors=True)


def test_absolute_sqlite_url_is_kept_and_parent_created(tmp_path):
    db = tmp_path / "a" / "b" / "x.db"
    assert Settings(DATABASE_URL=f"sqlite:///{db.as_posix()}").db_url == f"sqlite:///{db.as_posix()}"
    assert db.parent.is_dir()


def test_default_and_other_urls_are_untouched(tmp_path):
    s = Settings(DATABASE_URL="", DATA_DIR=str(tmp_path / "d"))
    assert s.db_url.endswith("/d/eval_harness.db") and Path(tmp_path / "d").is_dir()
    assert Settings(DATABASE_URL="postgresql+psycopg://u:p@h/db").db_url == "postgresql+psycopg://u:p@h/db"
    assert Settings(DATABASE_URL="sqlite:///:memory:").db_url == "sqlite:///:memory:"


def test_suite_is_hermetic_never_reads_the_real_dotenv():
    """The developer's .env holds real keys; tests must not see them (no network, no spend)."""
    from eval_harness.core.settings import USE_DOTENV
    from eval_harness.llm.settings import detect_provider

    assert USE_DOTENV is False and detect_provider() == "fake"
    for var in ("OPENROUTER_API_KEY", "TAVILY_API_KEY", "JUDGE_MODEL", "LANGSMITH_API_KEY", "LANGCHAIN_API_KEY"):
        assert not os.environ.get(var), var

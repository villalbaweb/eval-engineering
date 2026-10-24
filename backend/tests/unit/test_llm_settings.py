import pytest

from eval_harness.llm import settings as S


@pytest.fixture
def clean_env(monkeypatch):
    for v in list(__import__("os").environ):
        if v.endswith(("_MODEL", "_PROVIDER", "_API_KEY", "_BASE_URL", "_TEMPERATURE")) or v in ("GOOGLE_CLOUD_PROJECT",):
            monkeypatch.delenv(v, raising=False)
    return monkeypatch


def test_explicit_provider_wins_over_autodetect(clean_env):
    clean_env.setenv("GOOGLE_API_KEY", "g")
    clean_env.setenv("LLM_PROVIDER", "openrouter")
    assert S.detect_provider() == "openrouter"


def test_autodetect_order_google_first(clean_env):
    clean_env.setenv("OPENROUTER_API_KEY", "o")
    assert S.detect_provider() == "openrouter"
    clean_env.setenv("GOOGLE_API_KEY", "g")
    assert S.detect_provider() == "google"


def test_no_keys_means_offline_fake(clean_env):
    assert S.detect_provider() == "fake"


def test_unknown_provider_rejected(clean_env):
    clean_env.setenv("LLM_PROVIDER", "nope")
    with pytest.raises(ValueError):
        S.detect_provider()


def test_roles_resolve_independently(clean_env):
    clean_env.setenv("LLM_PROVIDER", "openrouter")
    clean_env.setenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
    clean_env.setenv("JUDGE_MODEL", "anthropic/claude-sonnet-4")
    a, j, s = S.resolve_role("agent"), S.resolve_role("judge"), S.resolve_role("synthesizer")
    assert (a.provider, a.model) == ("openrouter", "openai/gpt-4o-mini")
    assert j.model == "anthropic/claude-sonnet-4"
    assert s.model == j.model  # synthesizer falls back to the judge
    assert S.resolve_role("simulator").temperature > 0


def test_explicit_args_override_env(clean_env):
    clean_env.setenv("LLM_PROVIDER", "openrouter")
    clean_env.setenv("OPENROUTER_MODEL", "a/b")
    spec = S.resolve_role("agent", model="c/d", temperature=0.5)
    assert spec.model == "c/d" and spec.temperature == 0.5 and spec.slug == "openrouter:c/d"


def test_judge_requires_explicit_model_and_flags_self_judging(clean_env):
    clean_env.setenv("LLM_PROVIDER", "openrouter")
    clean_env.setenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
    assert not S.judge_configured()  # no JUDGE_MODEL -> model graders will be skipped
    clean_env.setenv("JUDGE_MODEL", "openai/gpt-4o-mini")
    assert S.judge_configured() and S.is_self_judged()
    clean_env.setenv("JUDGE_MODEL", "anthropic/claude-sonnet-4")
    assert not S.is_self_judged()


def test_factory_refuses_missing_model(clean_env):
    from eval_harness.llm.factory import make_chat_model

    clean_env.setenv("LLM_PROVIDER", "openrouter")
    with pytest.raises(RuntimeError, match="No model configured"):
        make_chat_model("agent")


def test_openrouter_model_is_built_without_network(clean_env):
    from eval_harness.llm.factory import make_chat_model

    clean_env.setenv("LLM_PROVIDER", "openrouter")
    clean_env.setenv("OPENROUTER_API_KEY", "sk-test")
    clean_env.setenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
    m = make_chat_model("agent")
    assert type(m).__name__ == "ChatOpenRouter" and m.model_name == "openai/gpt-4o-mini"

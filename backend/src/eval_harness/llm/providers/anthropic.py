from __future__ import annotations

from eval_harness.llm.settings import ModelSpec


def build(spec: ModelSpec):
    try:
        from langchain_anthropic import ChatAnthropic
    except ImportError as e:  # optional extra
        raise RuntimeError("Provider 'anthropic' needs its extra: uv sync --extra anthropic") from e
    kwargs = {"model": spec.model, "temperature": spec.temperature}
    return ChatAnthropic(**kwargs)

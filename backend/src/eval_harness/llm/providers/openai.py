from __future__ import annotations

from eval_harness.llm.settings import ModelSpec


def build(spec: ModelSpec):
    try:
        from langchain_openai import ChatOpenAI
    except ImportError as e:  # optional extra
        raise RuntimeError("Provider 'openai' needs its extra: uv sync --extra openai") from e
    kwargs = {"model": spec.model, "temperature": spec.temperature}
    return ChatOpenAI(**kwargs)

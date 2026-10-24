from __future__ import annotations

from eval_harness.llm.settings import ModelSpec


def build(spec: ModelSpec):
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
    except ImportError as e:  # optional extra
        raise RuntimeError("Provider 'google' needs its extra: uv sync --extra google") from e
    kwargs = {"model": spec.model, "temperature": spec.temperature}
    return ChatGoogleGenerativeAI(**kwargs)

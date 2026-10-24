from __future__ import annotations

import os

from langchain_openrouter import ChatOpenRouter

from eval_harness.llm.settings import ModelSpec


def build(spec: ModelSpec) -> ChatOpenRouter:
    kwargs = {
        "model": spec.model,
        "temperature": spec.temperature,
        "openrouter_api_key": os.environ.get("OPENROUTER_API_KEY", ""),
        "max_retries": 3,
    }
    if spec.base_url:
        kwargs["openrouter_api_base"] = spec.base_url
    return ChatOpenRouter(**kwargs)

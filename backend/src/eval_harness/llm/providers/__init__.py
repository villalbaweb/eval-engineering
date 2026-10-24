"""One module per provider. Each exposes ``build(spec) -> BaseChatModel``."""

from __future__ import annotations

import importlib

from langchain_core.language_models.chat_models import BaseChatModel

from eval_harness.llm.settings import ModelSpec

_MODULES = {
    "openrouter": "openrouter",
    "fake": "fake",
    "openai": "openai",
    "anthropic": "anthropic",
    "google": "google",
    "vertex": "vertex",
}


def build_provider_model(spec: ModelSpec) -> BaseChatModel:
    mod = importlib.import_module(f"eval_harness.llm.providers.{_MODULES[spec.provider]}")
    return mod.build(spec)

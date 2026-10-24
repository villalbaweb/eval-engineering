"""The ONLY place chat models are constructed."""

from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel

from eval_harness.llm.providers import build_provider_model
from eval_harness.llm.settings import ModelSpec, resolve_role


def make_chat_model(role: str = "agent", *, spec: ModelSpec | None = None, **override) -> BaseChatModel:
    spec = spec or resolve_role(role, **override)
    if not spec.model:
        raise RuntimeError(
            f"No model configured for role '{spec.role}' (provider '{spec.provider}'). "
            f"Set {spec.role.upper()}_MODEL or {spec.provider.upper()}_MODEL in .env."
        )
    return build_provider_model(spec)

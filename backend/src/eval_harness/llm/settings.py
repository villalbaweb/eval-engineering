"""Per-role model settings resolved from the environment.

Roles: ``agent`` (system under test), ``judge`` (LLM-as-judge graders),
``simulator`` (simulated users), ``synthesizer`` (synthetic data; defaults to judge).

Resolution for each role:
  provider -> ``<ROLE>_PROVIDER`` -> ``LLM_PROVIDER`` -> auto-detect (first key wins)
  model    -> ``<ROLE>_MODEL``    -> ``<PROVIDER>_MODEL``
"""

from __future__ import annotations

import os
from typing import Literal

from pydantic import BaseModel

from eval_harness.core import settings as _  # noqa: F401  (loads .env into os.environ)

Role = Literal["agent", "judge", "simulator", "synthesizer"]
ROLES: tuple[str, ...] = ("agent", "judge", "simulator", "synthesizer")

# Order matters for auto-detect: first configured key wins (Google first).
PROVIDER_ORDER = ("google", "openrouter", "anthropic", "openai", "vertex")
PROVIDER_KEYS = {
    "google": "GOOGLE_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "vertex": "GOOGLE_CLOUD_PROJECT",
}
# Offline provider for tests/demos; never auto-detected.
KNOWN_PROVIDERS = (*PROVIDER_ORDER, "fake")
ROLE_FALLBACK = {"synthesizer": "judge"}


class ModelSpec(BaseModel):
    """A fully resolved model choice. Recorded in every experiment snapshot."""

    role: str = "agent"
    provider: str
    model: str
    temperature: float = 0.0
    base_url: str | None = None

    @property
    def slug(self) -> str:
        return f"{self.provider}:{self.model}"


def _env(name: str) -> str:
    return os.environ.get(name, "").strip()


def detect_provider() -> str:
    explicit = _env("LLM_PROVIDER").lower()
    if explicit:
        if explicit not in KNOWN_PROVIDERS:
            raise ValueError(f"LLM_PROVIDER='{explicit}' not in {KNOWN_PROVIDERS}")
        return explicit
    for p in PROVIDER_ORDER:
        if _env(PROVIDER_KEYS[p]):
            return p
    return "fake"


def resolve_role(role: str, *, provider: str | None = None, model: str | None = None,
                 temperature: float | None = None) -> ModelSpec:
    """Resolve provider/model/temperature for a role; explicit args win over env."""
    if role not in ROLES:
        raise ValueError(f"unknown role '{role}', expected one of {ROLES}")
    R = role.upper()
    prov = (provider or _env(f"{R}_PROVIDER") or "").lower()
    if not prov and role in ROLE_FALLBACK:
        prov = (_env(f"{ROLE_FALLBACK[role].upper()}_PROVIDER") or "").lower()
    prov = prov or detect_provider()
    if prov not in KNOWN_PROVIDERS:
        raise ValueError(f"unknown provider '{prov}'")

    mdl = model or _env(f"{R}_MODEL")
    if not mdl and role in ROLE_FALLBACK:
        mdl = _env(f"{ROLE_FALLBACK[role].upper()}_MODEL")
    mdl = mdl or _env(f"{prov.upper()}_MODEL") or ("scripted" if prov == "fake" else "")

    if temperature is None:
        t = _env(f"{R}_TEMPERATURE")
        temperature = float(t) if t else (0.0 if role != "simulator" else 0.7)

    base_url = _env(f"{prov.upper()}_BASE_URL") or None
    return ModelSpec(role=role, provider=prov, model=mdl, temperature=temperature, base_url=base_url)


def judge_configured() -> bool:
    """Model graders need an explicit JUDGE_MODEL (so they never silently reuse the agent model).
    The offline ``fake`` provider is always considered configured."""
    return bool(_env("JUDGE_MODEL")) or resolve_role("judge").provider == "fake"


def is_self_judged() -> bool:
    a, j = resolve_role("agent"), resolve_role("judge")
    return a.provider != "fake" and a.provider == j.provider and a.model == j.model

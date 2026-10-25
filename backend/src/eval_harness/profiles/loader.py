"""Discover and load profiles and variants from ``evals/``.

Two layouts are supported, and they coexist:

* **profiles layout** - ``evals/profiles/<name>/profile.yaml`` + ``variants/*.yaml`` + the profile's own
  ``datasets/``, ``suites/``, ``rubrics/``... (``evals/rubrics/`` holds shared rubrics).
* **legacy layout** - the flat pre-profiles ``evals/`` folder (``evals/agents``, ``evals/suites``...). It is
  read as the implicit profile ``copilot`` whose root is ``evals/`` itself and whose variants are
  ``evals/agents/*.yaml``, unless ``evals/profiles/copilot/profile.yaml`` exists (i.e. it was migrated).
  Nothing has to move for anything to keep working; ``evalh migrate-profiles`` moves it when you choose to.
  Other profiles can live in ``evals/profiles/`` next to a legacy ``copilot``.

The **active profile** is, in order: the one set for the current request/command (:func:`use_profile`),
``EVAL_PROFILE``, ``copilot`` when it exists, else the first profile.
"""

from __future__ import annotations

import contextlib
import os
from collections.abc import Iterator
from contextvars import ContextVar
from pathlib import Path

import yaml

from eval_harness.evals.domain.profile import Inventory, Profile, Variant

DEFAULT_PROFILE = "copilot"
LEGACY_MARKERS = ("agents", "suites", "datasets")  # any of these at evals/ root = flat copilot content
_active: ContextVar[str | None] = ContextVar("eval_profile", default=None)


class ProfileNotFound(KeyError):
    def __str__(self) -> str:  # KeyError would quote the message
        return str(self.args[0])


class VariantNotFound(FileNotFoundError):
    pass


def _evals_dir() -> Path:
    from eval_harness.core.settings import get_settings

    return get_settings().evals_dir


def _profiles_dir(evals: Path | None = None) -> Path:
    return (evals or _evals_dir()) / "profiles"


def _folder_profiles(evals: Path) -> list[str]:
    return sorted(p.parent.name for p in _profiles_dir(evals).glob("*/profile.yaml"))


def _has_legacy_copilot(evals: Path) -> bool:
    return DEFAULT_PROFILE not in _folder_profiles(evals) and any((evals / m).is_dir() for m in LEGACY_MARKERS)


def profile_names(evals: Path | None = None) -> list[str]:
    evals = evals or _evals_dir()
    names = _folder_profiles(evals)
    if _has_legacy_copilot(evals):
        names = sorted({*names, DEFAULT_PROFILE})
    return names or [DEFAULT_PROFILE]  # an empty evals/ still behaves like the legacy copilot


def active_profile_name(evals: Path | None = None) -> str:
    names = profile_names(evals)
    want = _active.get() or os.environ.get("EVAL_PROFILE") or None
    if want:
        if want not in names:
            raise ProfileNotFound(f"profile '{want}' not found. Available: {names}")
        return want
    return DEFAULT_PROFILE if DEFAULT_PROFILE in names else names[0]


def is_legacy_layout(name: str | None = None, evals: Path | None = None) -> bool:
    """True when profile ``name`` (default: the active one) is the flat, not-yet-migrated copilot."""
    evals = evals or _evals_dir()
    name = name or active_profile_name(evals)
    return name == DEFAULT_PROFILE and DEFAULT_PROFILE not in _folder_profiles(evals)


@contextlib.contextmanager
def use_profile(name: str | None) -> Iterator[None]:
    """Make ``name`` the active profile for this context (request, CLI command, test). ``None`` = no-op.
    Contexts are copied into ``asyncio`` tasks and ``asyncio.to_thread`` workers, so trials inherit it."""
    if not name:
        yield
        return
    if name not in profile_names():
        raise ProfileNotFound(f"profile '{name}' not found. Available: {profile_names()}")
    tok = _active.set(name)
    try:
        yield
    finally:
        _active.reset(tok)


def set_active_profile(name: str | None) -> None:
    """Set the active profile for the rest of this context (CLI callback). Validated like use_profile."""
    if name and name not in profile_names():
        raise ProfileNotFound(f"profile '{name}' not found. Available: {profile_names()}")
    _active.set(name)


def profile_root(name: str | None = None, evals: Path | None = None) -> Path:
    evals = evals or _evals_dir()
    name = name or active_profile_name(evals)
    return evals if is_legacy_layout(name, evals) else _profiles_dir(evals) / name


def _read_yaml(p: Path) -> dict:
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


def load_profile(name: str | None = None) -> Profile:
    evals = _evals_dir()
    name = name or active_profile_name(evals)
    if name not in profile_names(evals):
        raise ProfileNotFound(f"profile '{name}' not found. Available: {profile_names(evals)}")
    if is_legacy_layout(name, evals):
        return Profile(name=DEFAULT_PROFILE, description="The lab's built-in Eval Copilot (legacy flat evals/ layout).",
                       inventory=Inventory(from_registry=True), legacy=True,
                       default_variant=_legacy_default_variant(evals))
    data = _read_yaml(_profiles_dir(evals) / name / "profile.yaml")
    data.pop("legacy", None)
    return Profile.model_validate({**data, "name": name})


def active_profile() -> Profile:
    return load_profile()


def list_profiles() -> list[Profile]:
    return [load_profile(n) for n in profile_names()]


def _legacy_default_variant(evals: Path) -> str | None:
    stems = sorted(p.stem for p in (evals / "agents").glob("*.yaml"))
    return "copilot-baseline" if "copilot-baseline" in stems else (stems[0] if stems else None)


def _legacy_variant(path: Path) -> Variant:
    data = _read_yaml(path)
    desc = data.pop("description", "")
    data.pop("name", None)  # the agent config keeps its own name (see agent.config)
    return Variant(name=path.stem, description=desc, target="local_agent", config=data)


def list_variants(profile: str | None = None) -> list[Variant]:
    evals = _evals_dir()
    name = profile or active_profile_name(evals)
    if name not in profile_names(evals):
        raise ProfileNotFound(f"profile '{name}' not found. Available: {profile_names(evals)}")
    if is_legacy_layout(name, evals):
        return [_legacy_variant(p) for p in sorted((evals / "agents").glob("*.yaml"))]
    out = []
    for p in sorted((_profiles_dir(evals) / name / "variants").glob("*.yaml")):
        out.append(Variant.model_validate({**_read_yaml(p), "name": p.stem}))
    return out


def resolve_variant(ref: str | None = None, profile: str | None = None) -> tuple[Profile, Variant]:
    """Find a variant by ``name``, ``alias`` or ``profile:variant``. ``None`` = the profile's default."""
    if ref and ":" in ref:
        profile, _, ref = ref.partition(":")
    prof = load_profile(profile)
    variants = list_variants(prof.name)
    if not ref:
        ref = prof.default_variant or (variants[0].name if variants else None)
    for v in variants:
        if v.name == ref:
            return prof, v
    for v in variants:
        if ref in v.aliases:
            return prof, v
    raise VariantNotFound(f"variant '{ref}' not found in profile '{prof.name}'. "
                          f"Available: {sorted(v.name for v in variants)}")

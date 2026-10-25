"""Agent profiles and their variants (what the UI's profile switcher and variant dropdowns use)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from eval_harness.evals.domain.profile import Profile, Variant
from eval_harness.evals.targets.base import CAPABILITIES, target_capabilities
from eval_harness.profiles import active_profile_name, list_profiles, list_variants

router = APIRouter(tags=["profiles"])

MODES = ["live", "multiturn", "trace", "replay"]


def variant_view(v: Variant) -> dict[str, Any]:
    caps = target_capabilities(v.target)
    return {"name": v.name, "description": v.description, "target": v.target, "aliases": v.aliases,
            # undeclared (pre-profiles plugin) targets are not gated; shown as 'rerun' only
            "capabilities": sorted(caps) if caps is not None else ["rerun"],
            "capabilities_declared": caps is not None}


def inventory_view(p: Profile) -> dict[str, Any]:
    from eval_harness.profiles.inventory import inventory

    return inventory(p)


def profile_view(p: Profile, active: str) -> dict[str, Any]:
    return {"name": p.name, "description": p.description, "active": p.name == active, "legacy_layout": p.legacy,
            "default_variant": p.default_variant, "variants": [variant_view(v) for v in list_variants(p.name)],
            "defaults": p.defaults.model_dump(), "traces": p.traces.model_dump(),
            "conventions": p.conventions.model_dump()}


@router.get("/profiles")
def profiles() -> dict[str, Any]:
    active = active_profile_name()
    return {"active": active, "modes": MODES, "capabilities": list(CAPABILITIES),
            "profiles": [profile_view(p, active) for p in list_profiles()]}

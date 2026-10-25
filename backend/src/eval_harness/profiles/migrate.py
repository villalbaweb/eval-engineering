"""Opt-in move from the legacy flat ``evals/`` layout to ``evals/profiles/copilot/``.

* dry run by default; ``apply=True`` moves; ``revert`` restores the flat layout byte for byte
* files are moved, never rewritten (git-ignored local data like ``datasets/accepted`` included)
* each ``agents/<x>.yaml`` becomes ``variants/<short>.yaml`` with ``aliases: [<x>]``, so every old
  agent name keeps resolving; the original file content is kept in the manifest for ``revert``
* suites are moved unchanged (their ``agent:`` names resolve through the aliases)
* running it twice is a no-op; the manifest is ``evals/profiles/.migration.json``
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from eval_harness.profiles.loader import DEFAULT_PROFILE

MOVED = ("datasets", "suites", "rubrics", "synthesis", "faults", "corpus", "cassettes", "candidates")
MANIFEST = ".migration.json"


@dataclass
class Plan:
    moves: list[tuple[str, str]] = field(default_factory=list)  # (src, dst) relative to evals/
    variants: list[tuple[str, str]] = field(default_factory=list)  # (agents/x.yaml, variants/short.yaml)
    created: list[str] = field(default_factory=list)
    note: str = ""


def _short(stem: str) -> str:
    return stem[len("copilot-"):] if stem.startswith("copilot-") and len(stem) > len("copilot-") else stem


def plan(evals: Path) -> Plan:
    prof = Path("profiles") / DEFAULT_PROFILE
    if (evals / prof / "profile.yaml").exists():
        return Plan(note=f"already migrated ({prof.as_posix()}/profile.yaml exists)")
    p = Plan()
    for name in MOVED:
        if (evals / name).exists():
            p.moves.append((name, (prof / name).as_posix()))
    for f in sorted((evals / "agents").glob("*.yaml")):
        p.variants.append((f"agents/{f.name}", (prof / "variants" / f"{_short(f.stem)}.yaml").as_posix()))
    p.created.append((prof / "profile.yaml").as_posix())
    if not p.moves and not p.variants:
        p.note = "nothing to migrate (no legacy evals/ content found)"
    return p


def _profile_yaml(default_variant: str | None) -> str:
    return yaml.safe_dump({
        "description": "The lab's built-in Eval Copilot (toy LangChain create_agent agent).",
        "default_variant": default_variant,
        "inventory": {"from_registry": True},
        # conventions omitted on purpose: the defaults ARE the copilot's rules
        "defaults": {"quick_suite": "smoke", "trace_suite": "traces", "trace_group": "traces",
                     "langsmith_prefix": "eval-eng"},  # keep existing LangSmith dataset names
    }, sort_keys=False)


def apply(evals: Path) -> Plan:
    p = plan(evals)
    if p.note:
        return p
    manifest: dict = {"moves": p.moves, "variants": [], "created": list(p.created)}
    variant_names = []
    for src, dst in p.variants:
        s, d = evals / src, evals / dst
        original = s.read_bytes().decode("utf-8")  # raw, so line endings survive a revert
        data = yaml.safe_load(original) or {}
        old_name = data.pop("name", s.stem)
        desc = data.pop("description", "")
        d.parent.mkdir(parents=True, exist_ok=True)
        d.write_text(yaml.safe_dump({"description": desc, "target": "local_agent",
                                     "aliases": sorted({s.stem, old_name}), "config": data},
                                    sort_keys=False, allow_unicode=True), encoding="utf-8")
        manifest["variants"].append({"src": src, "dst": dst, "original": original})
        variant_names.append(s.stem)
        s.unlink()
    agents = evals / "agents"
    if agents.is_dir() and not any(agents.iterdir()):
        agents.rmdir()
        manifest["removed_dirs"] = ["agents"]
    for src, dst in p.moves:
        (evals / dst).parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(evals / src), str(evals / dst))
    default = "copilot-baseline" if "copilot-baseline" in variant_names else (variant_names[0] if variant_names else None)
    (evals / p.created[0]).write_text(_profile_yaml(_short(default) if default else None), encoding="utf-8")
    (evals / "profiles" / MANIFEST).write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    return p


def revert(evals: Path) -> str:
    mf = evals / "profiles" / MANIFEST
    if not mf.exists():
        return "nothing to revert (no migration manifest)"
    m = json.loads(mf.read_text(encoding="utf-8"))
    for src, dst in reversed(m["moves"]):
        if (evals / dst).exists():
            shutil.move(str(evals / dst), str(evals / src))
    for d in m.get("removed_dirs", []):
        (evals / d).mkdir(exist_ok=True)
    for v in m["variants"]:
        (evals / v["src"]).parent.mkdir(parents=True, exist_ok=True)
        (evals / v["src"]).write_bytes(v["original"].encode("utf-8"))
        (evals / v["dst"]).unlink(missing_ok=True)
    for c in m["created"]:
        (evals / c).unlink(missing_ok=True)
    mf.unlink()
    for d in sorted((evals / "profiles").rglob("*"), key=lambda x: len(x.parts), reverse=True):
        if d.is_dir() and not any(d.iterdir()):
            d.rmdir()
    if (evals / "profiles").is_dir() and not any((evals / "profiles").iterdir()):
        (evals / "profiles").rmdir()
    return "reverted to the flat evals/ layout"

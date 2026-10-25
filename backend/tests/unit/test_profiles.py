"""Profiles and variants (P1): both layouts, active-profile resolution, aliases, opt-in reversible migration."""

import hashlib
import os
import shutil
from pathlib import Path

import pytest
from pydantic import ValidationError

from eval_harness.agent.config import list_agent_configs, load_agent_config
from eval_harness.core.settings import get_settings
from eval_harness.evals.domain.profile import Conventions, SkillRule, ToolErrorRule
from eval_harness.evals.graders.model.judge_base import load_rubric
from eval_harness.profiles import (
    ProfileNotFound,
    active_profile_name,
    is_legacy_layout,
    list_profiles,
    list_variants,
    load_profile,
    migrate,
    resolve_variant,
    use_profile,
)


@pytest.fixture()
def evals(tmp_path, tmp_evals):
    """A private evals/ copy (legacy layout) that settings point at for the duration of the test."""
    d = tmp_path / "evals"
    shutil.copytree(tmp_evals, d)
    s = get_settings()
    old = s.evals_dir
    s.evals_dir = d
    try:
        yield d
    finally:
        s.evals_dir = old


def tree(root: Path) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}


def test_legacy_layout_is_one_implicit_copilot_profile(evals):
    assert is_legacy_layout() and active_profile_name() == "copilot"
    prof = load_profile()
    assert prof.legacy and prof.inventory.from_registry and prof.default_variant == "copilot-baseline"
    assert [v.name for v in list_variants()] == ["copilot-baseline", "copilot-generic-loader", "copilot-no-skills"]
    s = get_settings()
    assert s.profile_dir == evals and s.datasets_dir == evals / "datasets" and s.faults_dir == evals / "faults"
    cfg = load_agent_config("copilot-baseline")
    assert cfg.name == "copilot-baseline" and cfg.skill_loader_mode == "per_skill"
    with pytest.raises(FileNotFoundError, match="Available"):
        load_agent_config("nope")


def test_migration_is_opt_in_reversible_and_idempotent(evals):
    (evals / "datasets" / "accepted").mkdir(exist_ok=True)  # git-ignored local data must move too
    (evals / "datasets" / "accepted" / "accepted.yaml").write_text("tasks: []\n", encoding="utf-8")
    before = tree(evals)

    dry = migrate.plan(evals)
    assert ("datasets", "profiles/copilot/datasets") in dry.moves and tree(evals) == before  # dry run: nothing moved

    migrate.apply(evals)
    assert not is_legacy_layout() and (evals / "profiles/copilot/datasets/accepted/accepted.yaml").exists()
    assert not (evals / "agents").exists() and not (evals / "datasets").exists()
    assert migrate.apply(evals).note.startswith("already migrated")  # twice = no-op

    migrate.revert(evals)
    assert tree(evals) == before  # byte-for-byte round trip


def test_migrated_variants_keep_old_names_and_configs(evals):
    legacy = {c.name: c.model_dump(exclude={"name", "description"}) for c in list_agent_configs()}
    migrate.apply(evals)
    prof, v = resolve_variant("copilot-baseline")  # old name = alias
    assert (prof.name, v.name, v.target) == ("copilot", "baseline", "local_agent")
    assert resolve_variant("copilot:no-skills")[1].name == "no-skills"
    assert resolve_variant()[1].name == "baseline"  # profile default
    assert load_profile().defaults.langsmith_prefix == "eval-eng"  # existing LangSmith dataset names kept
    for old, cfg in legacy.items():
        new = load_agent_config(old)  # every old name still loads the same configuration
        assert new.model_dump(exclude={"name", "description"}) == cfg
    assert get_settings().suites_dir == evals / "profiles/copilot/suites"


def test_active_profile_resolution(evals, monkeypatch):
    migrate.apply(evals)
    other = evals / "profiles" / "demo"
    (other / "variants").mkdir(parents=True)
    (other / "profile.yaml").write_text("description: second agent\n", encoding="utf-8")
    (other / "variants" / "logs.yaml").write_text("target: trace_source\n", encoding="utf-8")

    assert {"copilot", "demo"} <= {p.name for p in list_profiles()}
    assert active_profile_name() == "copilot"  # default when it exists
    with use_profile("demo"):
        assert active_profile_name() == "demo" and get_settings().datasets_dir == other / "datasets"
        assert resolve_variant()[1].name == "logs"
        with pytest.raises(FileNotFoundError, match="not an in-process agent"):
            load_agent_config("logs")
    assert active_profile_name() == "copilot"
    monkeypatch.setenv("EVAL_PROFILE", "demo")
    assert active_profile_name() == "demo"
    monkeypatch.setenv("EVAL_PROFILE", "missing")
    with pytest.raises(ProfileNotFound):
        active_profile_name()
    os.environ.pop("EVAL_PROFILE", None)
    with pytest.raises(ProfileNotFound), use_profile("missing"):
        pass


def test_legacy_copilot_coexists_with_folder_profiles(evals):
    """Adding another agent's profile must not hide (or move) the flat copilot."""
    other = evals / "profiles" / "demo"
    (other / "variants").mkdir(parents=True)
    (other / "profile.yaml").write_text("description: second agent\n", encoding="utf-8")
    assert {"copilot", "demo"} <= {p.name for p in list_profiles()}
    assert active_profile_name() == "copilot" and is_legacy_layout()
    assert get_settings().datasets_dir == evals / "datasets"  # copilot paths unchanged
    assert load_agent_config("copilot-baseline").name == "copilot-baseline"
    with use_profile("demo"):
        assert not is_legacy_layout() and get_settings().datasets_dir == other / "datasets"
    assert migrate.plan(evals).moves  # copilot can still be migrated later


def test_profile_rubrics_override_shared_ones(evals):
    migrate.apply(evals)
    (evals / "rubrics").mkdir(exist_ok=True)
    (evals / "rubrics" / "shared-only.md").write_text("shared", encoding="utf-8")
    (evals / "rubrics" / "conciseness.md").write_text("shared version", encoding="utf-8")
    assert load_rubric("shared-only") == "shared"
    assert load_rubric("conciseness") != "shared version"  # the profile's own rubric wins
    with pytest.raises(FileNotFoundError):
        load_rubric("missing")


def test_convention_rules_are_validated_and_default_to_the_lab_rules():
    c = Conventions()
    assert [r.tool_pattern for r in c.skills][0] == r"^load_skill_(?P<skill>.+)$"
    assert c.tool_error[0].result_prefix == "ERROR" and c.citations is not None
    with pytest.raises(ValidationError):
        SkillRule(tool="load_skill")  # tool rule needs arg
    with pytest.raises(ValidationError):
        ToolErrorRule(result_prefix="E", message_status="error")  # exactly one condition

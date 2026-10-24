"""Requirements as tests: >=5 tools, >=5 skills each with a loader tool, pluggable registries."""

import pytest

from eval_harness.evals.datasets.loader import dataset_groups, list_suites, load_tasks, suite_tasks
from eval_harness.evals.graders.base import grader_registry
from eval_harness.evals.metrics.registry import metric_registry
from eval_harness.skills.loader import load_library
from eval_harness.skills.tools import build_skill_tools
from eval_harness.tools.base import TOOL_SPECS, tool_registry


def test_at_least_five_general_tools():
    tool_registry.discover()
    general = set(TOOL_SPECS)
    assert len(general) >= 5
    assert {"web_search", "fetch_url", "knowledge_base_search", "stats_calculator", "current_datetime"} <= general


def test_at_least_five_skills_with_frontmatter():
    lib = load_library()
    assert len(lib) >= 5
    for s in lib.values():
        assert s.description and s.body


def test_each_skill_has_its_own_loader_tool_and_loads_body():
    lib = load_library()
    tools = {t.name: t for t in build_skill_tools(list(lib.values()), "per_skill")}
    for s in lib.values():
        assert s.tool_name in tools
        assert tools[s.tool_name].invoke({}) == s.body


def test_generic_loader_mode_and_unknown_skill():
    tools = {t.name: t for t in build_skill_tools(list(load_library().values()), "generic")}
    assert "load_skill" in tools and not any(n.startswith("load_skill_") for n in tools)
    assert tools["load_skill"].invoke({"name": "nope"}).startswith("ERROR")


def test_skill_assets_are_loadable_on_demand():
    lib = load_library()
    tools = {t.name: t for t in build_skill_tools(list(lib.values()), "generic")}
    assert "templates/rubric.md" in lib["rubric-authoring"].assets
    assert "Rubric" in tools["read_skill_asset"].invoke({"skill": "rubric-authoring", "path": "templates/rubric.md"})
    assert tools["read_skill_asset"].invoke({"skill": "rubric-authoring", "path": "../../x"}).startswith("ERROR")


def test_registries_are_populated():
    assert {"skill_selection", "trajectory_match", "llm_judge", "human_review", "pairwise_judge"} <= set(grader_registry.names())
    assert {"pass_rates", "by_tag", "flakiness", "cost_latency"} <= set(metric_registry.names())


def test_duplicate_registration_is_rejected():
    from eval_harness.core.registry import Registry

    r: Registry = Registry("thing")
    r.register("a")(object())
    with pytest.raises(ValueError):
        r.register("a")(object())


def test_every_suite_and_dataset_loads_and_references_known_graders():
    assert dataset_groups()
    known = set(grader_registry.names())
    for s in list_suites():
        assert {g.type for g in s.graders} <= known, s.name
        if s.target != "trace":
            assert suite_tasks(s) is not None


def test_task_ids_are_unique():
    ids = [t.id for t in load_tasks()]
    assert len(ids) == len(set(ids))

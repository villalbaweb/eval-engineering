from eval_harness.evals.analysis.compare import config_changes


def test_config_changes_lists_leaf_differences_and_ignores_noise():
    a = {"suite": {"agent": "baseline", "run": {"k": 1}}, "git_sha": "aaa", "tool_specs": {"x": 1},
         "target": {"agent_config": {"skills": "all"}, "skills": {"s1": 1, "s2": 2}}}
    b = {"suite": {"agent": "no-skills", "run": {"k": 3}}, "git_sha": "bbb", "tool_specs": {"x": 2},
         "target": {"agent_config": {"skills": "none"}, "skills": {}}}
    got = {c["path"]: (c["a"], c["b"]) for c in config_changes(a, b)}
    assert got["suite.agent"] == ("baseline", "no-skills")
    assert got["suite.run.k"] == ("1", "3")
    assert got["target.agent_config.skills"] == ("all", "none")
    assert "target.skills" in got and "2 entries" in got["target.skills"][0]  # summarized, not expanded
    assert not any(p.startswith(("git_sha", "tool_specs")) for p in got)


def test_identical_snapshots_have_no_changes():
    assert config_changes({"a": {"b": 1}}, {"a": {"b": 1}}) == []

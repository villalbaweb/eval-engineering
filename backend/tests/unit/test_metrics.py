import math

from eval_harness.evals.metrics import core


def test_pass_at_k_matches_formula():
    # n=10, c=6, k=3 -> 1 - C(4,3)/C(10,3) = 1 - 4/120
    assert math.isclose(core.pass_at_k(10, 6, 3), 1 - 4 / 120)
    assert core.pass_at_k(5, 0, 3) == 0.0
    assert core.pass_at_k(5, 5, 3) == 1.0
    assert core.pass_at_k(3, 1, 3) == 1.0  # n - c < k -> certain


def test_pass_pow_k_is_consistency_and_never_exceeds_pass_at_k():
    assert math.isclose(core.pass_pow_k(10, 6, 3), 0.6**3)
    for c in range(0, 11):
        assert core.pass_pow_k(10, c, 3) <= core.pass_at_k(10, c, 3) + 1e-12


def test_bootstrap_ci_contains_mean_and_is_deterministic():
    vals = [1, 1, 0, 1, 0, 1, 1, 1]
    m, lo, hi = core.bootstrap_ci(vals, seed=1)
    assert lo <= m <= hi
    assert core.bootstrap_ci(vals, seed=1) == (m, lo, hi)
    assert core.bootstrap_ci([1.0]) == (1.0, 1.0, 1.0)


def test_cohens_kappa():
    a = [True, True, False, False]
    assert core.cohens_kappa(a, a) == 1.0
    assert core.cohens_kappa(a, [not x for x in a]) == -1.0


def test_alignment_coverage_and_ffr():
    grader = [True, False, False, True, False]
    human = [True, True, False, False, False]  # humans: good, good, bad, bad, bad
    m = core.alignment(grader, human)
    assert math.isclose(m["coverage"], 2 / 3)  # bad outputs failed by grader: idx 2,4 of 2,3,4
    assert math.isclose(m["ffr"], 1 / 2)  # good outputs failed by grader: idx 1 of 0,1
    assert m["tp"] == 1 and m["tn"] == 2 and m["fp"] == 1 and m["fn"] == 1


def test_two_proportion_and_mcnemar():
    z, p = core.two_proportion_z(80, 100, 50, 100)
    assert p < 0.001 and z > 0
    assert core.two_proportion_z(5, 10, 5, 10) == (0.0, 1.0)
    _, p = core.mcnemar(10, 1)
    assert p < 0.05
    assert core.mcnemar(0, 0) == (0.0, 1.0)


def test_wilson_interval_bounds():
    lo, hi = core.wilson_interval(9, 10)
    assert 0 < lo < 0.9 < hi <= 1

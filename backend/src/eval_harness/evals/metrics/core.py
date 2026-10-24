"""Pure statistical functions used by the runner, the API and the stats tool."""

from __future__ import annotations

import math
import random
from collections.abc import Sequence


def pass_at_k(n: int, c: int, k: int) -> float:
    """Unbiased pass@k: probability that at least one of k samples (drawn from n trials,
    c of which passed) passes.  1 - C(n-c, k) / C(n, k)."""
    if n <= 0 or k <= 0:
        return 0.0
    k = min(k, n)
    if n - c < k:
        return 1.0
    return 1.0 - math.comb(n - c, k) / math.comb(n, k)


def pass_pow_k(n: int, c: int, k: int) -> float:
    """pass^k (consistency): probability that all k independent trials pass, (c/n)^k.

    This is the plug-in estimate; for exact k <= n you may prefer C(c,k)/C(n,k) - both are
    reported by :func:`pass_pow_k_exact`.
    """
    if n <= 0:
        return 0.0
    return (c / n) ** k


def pass_pow_k_exact(n: int, c: int, k: int) -> float:
    if n <= 0 or k > n:
        return 0.0
    return math.comb(c, k) / math.comb(n, k)


def mean(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def bootstrap_ci(values: Sequence[float], *, n_boot: int = 2000, alpha: float = 0.05,
                 seed: int | None = 0) -> tuple[float, float, float]:
    """Percentile bootstrap CI of the mean. Returns (mean, low, high)."""
    vals = list(values)
    if not vals:
        return 0.0, 0.0, 0.0
    rng = random.Random(seed)
    m = mean(vals)
    if len(vals) == 1:
        return m, m, m
    boots = sorted(mean([vals[rng.randrange(len(vals))] for _ in vals]) for _ in range(n_boot))
    lo = boots[int((alpha / 2) * n_boot)]
    hi = boots[min(n_boot - 1, int((1 - alpha / 2) * n_boot))]
    return m, lo, hi


def wilson_interval(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    p = successes / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, center - half), min(1.0, center + half)


def cohens_kappa(a: Sequence[bool], b: Sequence[bool]) -> float:
    """Chance-corrected agreement between two binary raters."""
    if len(a) != len(b) or not a:
        return 0.0
    n = len(a)
    po = sum(x == y for x, y in zip(a, b, strict=True)) / n
    pa, pb = sum(a) / n, sum(b) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def two_proportion_z(s1: int, n1: int, s2: int, n2: int) -> tuple[float, float]:
    """Two-sided z-test for a difference in proportions. Returns (z, p_value)."""
    if n1 == 0 or n2 == 0:
        return 0.0, 1.0
    p1, p2 = s1 / n1, s2 / n2
    p = (s1 + s2) / (n1 + n2)
    se = math.sqrt(p * (1 - p) * (1 / n1 + 1 / n2))
    if se == 0:
        return 0.0, 1.0
    z = (p1 - p2) / se
    return z, math.erfc(abs(z) / math.sqrt(2))


def mcnemar(b: int, c: int) -> tuple[float, float]:
    """McNemar's test (continuity-corrected) on discordant pairs. b: A pass/B fail, c: A fail/B pass."""
    if b + c == 0:
        return 0.0, 1.0
    chi2 = (abs(b - c) - 1) ** 2 / (b + c)
    return chi2, math.erfc(math.sqrt(chi2 / 2))


def alignment(grader_pass: Sequence[bool], human_pass: Sequence[bool]) -> dict[str, float]:
    """Validate-the-validator metrics (EvalGen).

    coverage = share of human-bad outputs the grader also fails (true negative rate)
    ffr      = false failure rate: share of human-good outputs the grader fails
    alignment = harmonic mean of coverage and (1 - ffr)
    """
    bad = [(g, h) for g, h in zip(grader_pass, human_pass, strict=True) if not h]
    good = [(g, h) for g, h in zip(grader_pass, human_pass, strict=True) if h]
    coverage = sum(1 for g, _ in bad if not g) / len(bad) if bad else float("nan")
    ffr = sum(1 for g, _ in good if not g) / len(good) if good else float("nan")
    inv = 1 - ffr if not math.isnan(ffr) else float("nan")
    if math.isnan(coverage) or math.isnan(inv) or (coverage + inv) == 0:
        align = float("nan")
    else:
        align = 2 * coverage * inv / (coverage + inv)
    tp = sum(1 for g, h in zip(grader_pass, human_pass, strict=True) if g and h)
    tn = sum(1 for g, h in zip(grader_pass, human_pass, strict=True) if not g and not h)
    fp = sum(1 for g, h in zip(grader_pass, human_pass, strict=True) if g and not h)
    fn = sum(1 for g, h in zip(grader_pass, human_pass, strict=True) if not g and h)
    return {
        "coverage": coverage, "ffr": ffr, "alignment": align,
        "kappa": cohens_kappa(grader_pass, human_pass),
        "tp": tp, "tn": tn, "fp": fp, "fn": fn, "n": len(grader_pass),
    }


def percentile(xs: Sequence[float], q: float) -> float:
    if not xs:
        return 0.0
    s = sorted(xs)
    idx = min(len(s) - 1, max(0, round(q * (len(s) - 1))))
    return s[idx]

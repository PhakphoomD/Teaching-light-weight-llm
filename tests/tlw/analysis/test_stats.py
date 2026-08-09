"""Statistical correctness tests for stats.py (T2.8 teaching-loop-protocol.md §4).

Every non-trivial number here is either hand-computable (worked in the
docstring/comment) or cross-checked against an independent implementation
(scipy.stats.binomtest for McNemar; a from-scratch Wilson formula written
fresh in this file, not imported from stats.py) -- scipy is already
installed in the tlw env; it is used here ONLY as a test-time cross-check,
never imported by src/tlw/analysis (stdlib+numpy only, T2.8 build rule 6)."""

import math

import numpy as np
import pytest

from src.tlw.analysis.stats import (
    exact_mcnemar,
    paired_cluster_bootstrap,
    per_seed_deltas,
    wilson_interval,
)


# --- Wilson interval -----------------------------------------------------------


def _independent_wilson(k: int, n: int, z: float = 1.959963984540054):
    """A from-scratch re-derivation of the Wilson score interval (different
    algebraic grouping than stats.py's), used purely to cross-check --
    catches a typo'd formula that property tests alone would miss."""
    p = k / n
    z2 = z * z
    denom = 1 + z2 / n
    centre = p + z2 / (2 * n)
    adj = z * math.sqrt((p * (1 - p) + z2 / (4 * n)) / n)
    return (centre - adj) / denom, (centre + adj) / denom


@pytest.mark.parametrize("k,n", [(0, 10), (10, 10), (5, 20), (3, 125), (62, 125), (125, 125)])
def test_wilson_matches_independent_reimplementation(k, n):
    result = wilson_interval(k, n)
    exp_low, exp_high = _independent_wilson(k, n)
    assert result.low == pytest.approx(max(0.0, exp_low), abs=1e-9)
    assert result.high == pytest.approx(min(1.0, exp_high), abs=1e-9)


def test_wilson_interval_contains_point_estimate():
    for k, n in [(1, 3), (62, 125), (0, 5), (5, 5)]:
        result = wilson_interval(k, n)
        assert result.low <= result.point <= result.high


def test_wilson_zero_n_is_defined_not_a_crash():
    result = wilson_interval(0, 0)
    assert result.point == 0.0
    assert result.low == 0.0
    assert result.high == 0.0


def test_wilson_rejects_invalid_inputs():
    with pytest.raises(ValueError):
        wilson_interval(-1, 5)
    with pytest.raises(ValueError):
        wilson_interval(6, 5)


def test_wilson_bounds_within_unit_interval():
    for k, n in [(0, 1), (1, 1), (50, 50), (1, 1000)]:
        result = wilson_interval(k, n)
        assert 0.0 <= result.low <= 1.0
        assert 0.0 <= result.high <= 1.0


# --- paired cluster bootstrap ----------------------------------------------------


def test_bootstrap_hand_computable_two_cluster_example():
    """2 questions, 1 replicate each: q1 both arms pass (delta contribution
    0); q2 arm_a passes, arm_b fails (delta contribution +1). Resampling 2
    clusters with replacement from {q1, q2} gives 4 equally-likely draws:
    (q1,q1)->delta 0, (q1,q2)->0.5, (q2,q1)->0.5, (q2,q2)->1.0 -- so the
    delta distribution is {0: .25, 0.5: .5, 1.0: .25}. With 20000 resamples
    the 2.5th/97.5th percentiles land exactly on 0.0/1.0 (verified live,
    deterministic for seed=0)."""
    cluster_table = {
        "q1": {"a": [True], "b": [True]},
        "q2": {"a": [True], "b": [False]},
    }
    result = paired_cluster_bootstrap(cluster_table, "a", "b", n_resamples=20_000, seed=0)
    assert result.point_estimate == pytest.approx(0.5)
    assert result.ci_low == pytest.approx(0.0, abs=1e-9)
    assert result.ci_high == pytest.approx(1.0, abs=1e-9)
    assert result.n_clusters == 2


def test_bootstrap_is_deterministic_given_seed():
    cluster_table = {f"q{i}": {"a": [i % 2 == 0], "b": [i % 3 == 0]} for i in range(30)}
    r1 = paired_cluster_bootstrap(cluster_table, "a", "b", n_resamples=2000, seed=7)
    r2 = paired_cluster_bootstrap(cluster_table, "a", "b", n_resamples=2000, seed=7)
    assert r1 == r2


def test_bootstrap_different_seed_can_differ_but_same_point_estimate():
    cluster_table = {f"q{i}": {"a": [i % 2 == 0], "b": [i % 3 == 0]} for i in range(30)}
    r1 = paired_cluster_bootstrap(cluster_table, "a", "b", n_resamples=2000, seed=1)
    r2 = paired_cluster_bootstrap(cluster_table, "a", "b", n_resamples=2000, seed=2)
    assert r1.point_estimate == pytest.approx(r2.point_estimate)


def test_bootstrap_ci_contains_point_estimate_property():
    rng = np.random.default_rng(123)
    for trial in range(10):
        n_q = rng.integers(5, 40)
        cluster_table = {}
        for i in range(n_q):
            n_seeds = rng.integers(1, 4)
            cluster_table[f"q{i}"] = {
                "a": [bool(rng.integers(0, 2)) for _ in range(n_seeds)],
                "b": [bool(rng.integers(0, 2)) for _ in range(n_seeds)],
            }
        result = paired_cluster_bootstrap(cluster_table, "a", "b", n_resamples=2000, seed=trial)
        assert result.ci_low <= result.point_estimate <= result.ci_high


def test_bootstrap_degenerate_all_pass_vs_all_fail_arm():
    """arm_a passes every question, arm_b fails every question: the delta
    is 1.0 on EVERY resample (no variance possible) -- CI must collapse to
    a point, not error or silently widen."""
    cluster_table = {f"q{i}": {"a": [True, True, True], "b": [False, False, False]} for i in range(15)}
    result = paired_cluster_bootstrap(cluster_table, "a", "b", n_resamples=1000, seed=0)
    assert result.point_estimate == pytest.approx(1.0)
    assert result.ci_low == pytest.approx(1.0)
    assert result.ci_high == pytest.approx(1.0)
    assert not result.crosses_zero()


def test_bootstrap_no_effect_arms_identical_crosses_zero():
    cluster_table = {f"q{i}": {"a": [i % 2 == 0], "b": [i % 2 == 0]} for i in range(50)}
    result = paired_cluster_bootstrap(cluster_table, "a", "b", n_resamples=5000, seed=0)
    assert result.point_estimate == pytest.approx(0.0)
    assert result.crosses_zero()


def test_bootstrap_raises_on_no_paired_questions():
    cluster_table = {"q1": {"a": [True]}, "q2": {"b": [True]}}  # no question has BOTH arms
    with pytest.raises(ValueError):
        paired_cluster_bootstrap(cluster_table, "a", "b")


def test_bootstrap_ignores_unpaired_questions():
    """A question that only has data for one arm must not silently enter
    the paired comparison (n_clusters should exclude it)."""
    cluster_table = {
        "paired_1": {"a": [True], "b": [False]},
        "paired_2": {"a": [False], "b": [False]},
        "unpaired": {"a": [True]},  # arm b never ran this question
    }
    result = paired_cluster_bootstrap(cluster_table, "a", "b", n_resamples=500, seed=0)
    assert result.n_clusters == 2


# --- exact McNemar ---------------------------------------------------------------


def test_mcnemar_hand_computable_b3_c1():
    """b=3 (a-pass/b-fail), c=1 (a-fail/b-pass): n=4, k=min(b,c)=1.
    P(X<=1 | Binomial(4, 0.5)) = (C(4,0)+C(4,1))/16 = 5/16 = 0.3125;
    two-sided p = 2*0.3125 = 0.625 -- matches scipy.stats.binomtest(1, 4,
    0.5, alternative='two-sided').pvalue == 0.625 (verified live)."""
    pairs = [(True, False)] * 3 + [(False, True)] * 1 + [(True, True)] * 2 + [(False, False)] * 5
    result = exact_mcnemar(pairs)
    assert result.b == 3
    assert result.c == 1
    assert result.p_value == pytest.approx(0.625, abs=1e-9)


def test_mcnemar_matches_scipy_binomtest_cross_check():
    scipy_stats = pytest.importorskip("scipy.stats")
    for b, c in [(0, 0), (1, 0), (0, 1), (5, 5), (10, 2), (3, 7)]:
        pairs = [(True, False)] * b + [(False, True)] * c
        result = exact_mcnemar(pairs)
        if b + c == 0:
            assert result.p_value == 1.0
            continue
        expected = scipy_stats.binomtest(min(b, c), b + c, 0.5, alternative="two-sided").pvalue
        assert result.p_value == pytest.approx(expected, abs=1e-9)


def test_mcnemar_no_discordant_pairs_is_p_one():
    pairs = [(True, True), (False, False), (True, True)]
    result = exact_mcnemar(pairs)
    assert result.b == 0
    assert result.c == 0
    assert result.p_value == 1.0


def test_mcnemar_symmetric_in_b_c():
    pairs_bc = [(True, False)] * 6 + [(False, True)] * 2
    pairs_cb = [(True, False)] * 2 + [(False, True)] * 6
    assert exact_mcnemar(pairs_bc).p_value == pytest.approx(exact_mcnemar(pairs_cb).p_value)


# --- per-seed deltas ---------------------------------------------------------------


def test_per_seed_deltas_basic():
    cluster_table = {
        "q1": {"a": [True, False], "b": [False, False]},
        "q2": {"a": [True, True], "b": [True, False]},
    }
    seed_index = {
        "q1": {"a": [13, 42], "b": [13, 42]},
        "q2": {"a": [13, 42], "b": [13, 42]},
    }
    deltas = per_seed_deltas(cluster_table, "a", "b", [13, 42], seed_index)
    # seed 13: a-pass = q1(T)+q2(T)=2/2=1.0 ; b-pass = q1(F)+q2(T)=1/2=0.5 -> delta 0.5
    # seed 42: a-pass = q1(F)+q2(T)=1/2=0.5 ; b-pass = q1(F)+q2(F)=0/2=0.0 -> delta 0.5
    assert deltas[13] == pytest.approx(0.5)
    assert deltas[42] == pytest.approx(0.5)


def test_per_seed_deltas_omits_seed_with_no_paired_data():
    cluster_table = {"q1": {"a": [True]}}
    seed_index = {"q1": {"a": [99]}}
    deltas = per_seed_deltas(cluster_table, "a", "b", [99], seed_index)
    assert 99 not in deltas

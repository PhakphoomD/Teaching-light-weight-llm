"""Report-assembly tests (T2.8 step 2 + honesty banner, build rules 3-4)."""

import pytest

from src.tlw.analysis.loaders import ConflationError, discover_runs
from src.tlw.analysis.report import (
    PRE_REGISTERED_N_QUESTIONS,
    PRE_REGISTERED_N_SEEDS,
    arm_descriptive,
    banner_for,
    build_comparison,
    build_report,
    memory_note_usage,
    not_pre_registered_reasons,
    pooled_pass_rate,
    reference_match_divergence,
    rounds_to_pass_distribution,
    token_cost_per_arm,
)
from src.tlw.analysis.loaders import select_arm_runs


def _make_full_pilot(runs_root, make_run):
    """3 arms x 3 seeds, 5 questions each -- shaped like a real pilot but
    far short of the pre-registered 125q x 3seed headline sample."""
    for seed in (13, 42, 123):
        make_run(f"armA__seed{seed}", arm="A", seed=seed, memory_type="none", passed_flags=[True, False, True, True, False])
        make_run(f"armB__seed{seed}", arm="B", seed=seed, memory_type="none", passed_flags=[True, True, True, False, False])
        make_run(f"armC__seed{seed}", arm="C", seed=seed, memory_type="none", passed_flags=[True, True, True, True, False])
    return discover_runs(runs_root)


# --- descriptive -------------------------------------------------------------------


def test_pooled_pass_rate_sums_across_seeds(runs_root, make_run):
    runs = _make_full_pilot(runs_root, make_run)
    runs_a = select_arm_runs(runs, "A", "none")
    k, n = pooled_pass_rate(runs_a)
    assert n == 15  # 3 seeds x 5 questions
    assert k == 9  # 3 pass each seed x 3 seeds ([True, False, True, True, False] -> 3 passes)


def test_arm_descriptive_returns_wilson_per_arm(runs_root, make_run):
    runs = _make_full_pilot(runs_root, make_run)
    runs_by_arm = {arm: select_arm_runs(runs, arm, "none") for arm in ("A", "B", "C")}
    descriptive = arm_descriptive(runs_by_arm)
    assert set(descriptive) == {"A", "B", "C"}
    for wi in descriptive.values():
        assert wi.low <= wi.point <= wi.high


# --- honesty banner ----------------------------------------------------------------


def test_banner_triggers_on_pilot_sized_data(runs_root, make_run):
    runs = _make_full_pilot(runs_root, make_run)
    reasons = not_pre_registered_reasons(runs)
    assert reasons  # both n<125 and (here) seeds are actually 3 -- n reason must fire
    banner = banner_for(runs)
    assert banner is not None
    assert "NOT the pre-registered sample" in banner


def test_banner_absent_when_sample_meets_pre_registration(runs_root, make_run):
    passed = [True] * 62 + [False] * 63  # 125 questions
    for seed in (13, 42, 123):
        make_run(f"armC__seed{seed}", arm="C", seed=seed, memory_type="none", passed_flags=passed)
    runs = discover_runs(runs_root)
    banner = banner_for(runs)
    assert banner is None


def test_banner_fires_on_seed_shortfall_even_with_full_n(runs_root, make_run):
    passed = [True] * 62 + [False] * 63
    make_run("armC__seed42_only", arm="C", seed=42, memory_type="none", passed_flags=passed)
    runs = discover_runs(runs_root)
    reasons = not_pre_registered_reasons(runs)
    assert any("seed" in r for r in reasons)


def test_pre_registered_constants_match_eval_spec():
    # EVAL_SPEC.md §4.4 (125 held-out) / §4.1 (3 seeds: 13, 42, 123)
    assert PRE_REGISTERED_N_QUESTIONS == 125
    assert PRE_REGISTERED_N_SEEDS == 3


# --- comparisons / V8 --------------------------------------------------------------


def test_build_comparison_headline_c_minus_b(runs_root, make_run):
    runs = _make_full_pilot(runs_root, make_run)
    comparison = build_comparison(runs, "C", "B", memory_type="none", n_resamples=1000, seed=0)
    assert comparison.arm_a == "C"
    assert comparison.arm_b == "B"
    assert comparison.bootstrap.ci_low <= comparison.bootstrap.point_estimate <= comparison.bootstrap.ci_high
    assert comparison.banner is not None  # pilot-sized, must carry the banner


def test_build_comparison_raises_value_error_when_arm_missing(runs_root, make_run):
    make_run("armC__seed42", arm="C", seed=42, memory_type="none", passed_flags=[True, False])
    runs = discover_runs(runs_root)
    with pytest.raises(ValueError):
        build_comparison(runs, "C", "B", memory_type="none")


def test_build_report_refuses_mixed_memory_for_one_arm(runs_root, make_run):
    """If arm C has BOTH a headline (none) and an ablation (faiss) run
    discoverable, selecting memory_type='none' must still only see the
    'none' one -- and if a caller bypasses select_arm_runs and hands mixed
    runs straight to build_comparison, it must raise, not silently pool."""
    make_run("armC_none__seed42", arm="C", seed=42, memory_type="none", passed_flags=[True, False])
    make_run("armC_faiss__seed42", arm="C", seed=42, memory_type="faiss", passed_flags=[True, True])
    make_run("armB_none__seed42", arm="B", seed=42, memory_type="none", passed_flags=[False, True])
    runs = discover_runs(runs_root)

    # The public path (memory_type filter) must not conflate:
    comparison = build_comparison(runs, "C", "B", memory_type="none", n_resamples=500, seed=0)
    assert comparison.memory_type == "none"

    # And the low-level guard used internally must actively reject a
    # hand-mixed list (defense in depth, not just filter-and-hope).
    from src.tlw.analysis.loaders import assert_single_memory_type

    mixed = [r for r in runs if r.arm == "C"]
    with pytest.raises(ConflationError):
        assert_single_memory_type(mixed)


def test_build_report_end_to_end_smoke(runs_root, make_run):
    runs = _make_full_pilot(runs_root, make_run)
    report = build_report(runs, comparisons=[("C", "B"), ("B", "A")], memory_type="none", n_resamples=500, seed=0)
    assert report["arms_present"] == ["A", "B", "C"]
    assert set(report["comparisons"]) == {"C-B", "B-A"}
    assert report["banner"] is not None
    # correctness and reference_match must be separate keys, never merged
    for arm, row in report["reference_match"].items():
        assert set(row) == {
            "correctness_pass_rate",
            "reference_match_semantic_sim_mean",
            "reference_match_rouge_l_mean",
        }


def test_build_report_records_error_for_missing_comparison_arm(runs_root, make_run):
    make_run("armC__seed42", arm="C", seed=42, memory_type="none", passed_flags=[True, False])
    runs = discover_runs(runs_root)
    report = build_report(runs, comparisons=[("D", "C")], memory_type="none", n_resamples=200, seed=0)
    assert "D-C" in report["comparison_errors"]
    assert "D-C" not in report["comparisons"]


# --- secondary views ----------------------------------------------------------------


def test_reference_match_never_merged_into_correctness(runs_root, make_run):
    runs = _make_full_pilot(runs_root, make_run)
    runs_by_arm = {arm: select_arm_runs(runs, arm, "none") for arm in ("A", "B", "C")}
    div = reference_match_divergence(runs_by_arm)
    for arm, row in div.items():
        # correctness_pass_rate must come from passed_count/num_questions,
        # never be computed from semantic_sim/rouge_l.
        k, n = pooled_pass_rate(runs_by_arm[arm])
        assert row["correctness_pass_rate"] == pytest.approx(k / n)


def test_rounds_to_pass_distribution_counts_first_passing_round(runs_root, make_run):
    make_run(
        "armC__seed42",
        arm="C",
        seed=42,
        passed_flags=[True, False],
        rounds_per_question=[2, 3],
    )
    runs = discover_runs(runs_root)
    dist = rounds_to_pass_distribution(select_arm_runs(runs, "C", "none"))
    # question 0 passes on its final (2nd) round -> bucket "2"
    # question 1 never passes -> bucket "never"
    assert dist.get("2") == 1
    assert dist.get("never") == 1


def test_token_cost_per_arm_sums_all_roles(runs_root, make_run):
    make_run("armC__seed42", arm="C", seed=42, passed_flags=[True], student_tokens=100, teacher_tokens=200, judge_tokens=50)
    runs = discover_runs(runs_root)
    costs = token_cost_per_arm({"C": select_arm_runs(runs, "C", "none")})
    assert costs["C"]["student"] == 100
    assert costs["C"]["teacher"] == 200
    assert costs["C"]["judge"] == 50
    assert costs["C"]["total"] == 350


def test_memory_note_usage_zero_for_headline_none_arms(runs_root, make_run):
    make_run("armA__seed42", arm="A", seed=42, memory_type="none", passed_flags=[True, True])
    runs = discover_runs(runs_root)
    usage = memory_note_usage({"A": select_arm_runs(runs, "A", "none")})
    assert usage["A"]["rounds_using_memory"] == 0
    assert usage["A"]["memory_hit_rate"] == 0.0


def test_memory_note_usage_counts_flagged_rounds(runs_root, make_run):
    make_run(
        "armC_faiss__seed42",
        arm="C",
        seed=42,
        memory_type="faiss",
        passed_flags=[True, True],
        memory_used_flags=[True, False],
        memory_episodes=4,
        memory_rejects=1,
    )
    runs = discover_runs(runs_root)
    usage = memory_note_usage({"C": select_arm_runs(runs, "C", "faiss")})
    assert usage["C"]["rounds_using_memory"] == 1
    assert usage["C"]["total_rounds"] == 2
    assert usage["C"]["memory_hit_rate"] == pytest.approx(0.5)
    assert usage["C"]["total_episodes_stored"] == 4
    assert usage["C"]["total_rejects"] == 1

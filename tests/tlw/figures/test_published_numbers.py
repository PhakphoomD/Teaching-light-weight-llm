"""Does what the figures draw still equal what the documents publish?

This is the guard the previous figure script did not have. That script carried
its numbers as literals transcribed by hand out of `docs/RAG_LAW.md`, so a
regenerated log and a published claim could drift apart indefinitely and
nothing would notice. Here each expectation is written down once, recomputed
from the committed artifact, and compared -- so the failure mode becomes a red
test rather than a confident chart of a stale number.

The expected values are quoted from the reports, with the source named on each
case, and are deliberately NOT derived from the same code path they check.

Skipped, not failed, when `runs/` is absent: raw generations are gitignored and
a fresh clone legitimately lacks them. A *present but changed* layout must fail
-- see `test_evidence_layout_has_not_moved`.
"""

from __future__ import annotations

import re

import pytest

from src.tlw.figures import data as D

pytestmark = pytest.mark.skipif(
    not (D.RUNS / "rag-wixqa").is_dir() or not (D.RUNS / "teaching-loop-medquad").is_dir(),
    reason="run artifacts are gitignored; recompute checks need a populated runs/",
)

TOLERANCE = 0.0015  # published values are quoted to three decimals


# --------------------------------------------------------------------------
# O1 -- the teaching loop (docs/EXPERIMENT_RESULTS.md §7.1)
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "condition,published",
    [
        ("1-baseline", 0.821),
        ("2-self-refine", 0.912),
        ("3-teacher-feedback", 0.915),
        ("4-teacher-sees-answer", 0.940),
    ],
)
def test_track_a_arm_levels(condition, published):
    assert D.study_pass_rate("teaching-loop-medquad", condition).point == pytest.approx(
        published, abs=TOLERANCE
    )


def test_teacher_adds_nothing_over_self_refinement():
    """ADR-024's headline: +0.003 [-0.021, +0.029], McNemar p = 1.00."""
    c = D.study_comparison("teaching-loop-medquad", "3-teacher-feedback", "2-self-refine")
    assert c.delta.point_estimate == pytest.approx(0.003, abs=TOLERANCE)
    assert c.delta.crosses_zero()
    assert c.mcnemar.p_value == pytest.approx(1.00, abs=0.01)
    assert (c.mcnemar.b, c.mcnemar.c) == (16, 15)


def test_self_refinement_is_a_real_gain():
    c = D.study_comparison("teaching-loop-medquad", "2-self-refine", "1-baseline")
    assert c.delta.point_estimate == pytest.approx(0.091, abs=TOLERANCE)
    assert not c.delta.crosses_zero()
    assert (c.mcnemar.b, c.mcnemar.c) == (43, 9)


# --------------------------------------------------------------------------
# O3 -- retrieval on a known domain (docs/EXPERIMENT_RESULTS.md §7.2)
# --------------------------------------------------------------------------


def test_retrieval_has_no_net_effect_on_the_small_model():
    c = D.study_comparison("rag-medquad", "small-model-with-rag", "small-model-no-rag")
    assert c.delta.point_estimate == pytest.approx(-0.005, abs=TOLERANCE)
    assert c.delta.crosses_zero()
    assert (c.fixed, c.broke) == (37, 39)


def test_retrieval_significantly_harms_the_larger_model():
    c = D.study_comparison("rag-medquad", "large-model-with-rag", "large-model-no-rag")
    assert c.delta.point_estimate == pytest.approx(-0.069, abs=TOLERANCE)
    assert not c.delta.crosses_zero()


def test_the_null_is_two_effects_cancelling():
    """The aggregate hides a gradient: repairs land where the baseline never
    succeeded, regressions where it always did."""
    buckets = D.study_outcome_by_reliability(
        "rag-medquad", "small-model-with-rag", "small-model-no-rag"
    )
    assert buckets["never"]["fixed"] == 15
    assert buckets["never"]["broke"] == 0
    assert buckets["always"]["broke"] == 35
    assert buckets["always"]["fixed"] == 0


# --------------------------------------------------------------------------
# O4/O5 -- WixQA (docs/EXPERIMENT_RESULTS.md §7.4-7.6)
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "step,published",
    [
        ("no-rag", 0.163),
        ("rag-basic", 0.315),
        ("rag-better-retriever", 0.340),
        ("rag-wider-context", 0.470),
    ],
)
def test_wixqa_ladder_levels(step, published):
    assert D.wixqa_pass_rate(step).point == pytest.approx(published, abs=TOLERANCE)


def test_retrieval_helps_where_the_model_lacks_the_knowledge():
    c = D.wixqa_comparison("rag-basic", "no-rag")
    assert c.delta.point_estimate == pytest.approx(0.152, abs=TOLERANCE)
    assert not c.delta.crosses_zero()
    assert c.mcnemar.p_value < 1e-9


def test_the_lift_is_the_retrieved_data():
    """The causal split: same system, opposite outcome, decided only by
    whether the retrieved text held the answer."""
    gold = D.wixqa_gold_retrieved("rag-basic")
    got = D.wixqa_comparison("rag-basic", "no-rag", subset=gold, want=True)
    missed = D.wixqa_comparison("rag-basic", "no-rag", subset=gold, want=False)
    assert got.wilson_b.point == pytest.approx(0.127, abs=TOLERANCE)
    assert got.wilson_a.point == pytest.approx(0.400, abs=TOLERANCE)
    assert got.delta.point_estimate == pytest.approx(0.273, abs=TOLERANCE)
    assert missed.delta.point_estimate == pytest.approx(0.004, abs=TOLERANCE)
    assert missed.delta.crosses_zero()


@pytest.mark.parametrize("step,published", [("rag-basic", 0.550), ("rag-wider-context", 0.665)])
def test_retrieval_hit_rates(step, published):
    assert D.wixqa_hit_rate(step).value == pytest.approx(published, abs=TOLERANCE)


def test_the_retriever_changes_frequency_not_payoff():
    """P(pass | the answer was retrieved) is near-identical across the two
    retrievers -- the mechanism behind the dose-response."""
    basic, _ = D.wixqa_conditional_pass("rag-basic")
    better, _ = D.wixqa_conditional_pass("rag-better-retriever")
    assert basic.point == pytest.approx(0.400, abs=TOLERANCE)
    assert better.point == pytest.approx(0.411, abs=TOLERANCE)


def test_delivery_outweighs_the_retriever():
    """The project's largest single finding, and the reason both effects must
    be shown together: the interval on one excludes zero and the other does
    not, despite the smaller one being the more intuitive lever."""
    retriever = D.wixqa_comparison("rag-better-retriever", "rag-basic")
    delivery = D.wixqa_comparison("rag-wider-context", "rag-better-retriever")
    assert retriever.delta.point_estimate == pytest.approx(0.025, abs=TOLERANCE)
    assert retriever.delta.crosses_zero()
    assert delivery.delta.point_estimate == pytest.approx(0.130, abs=TOLERANCE)
    assert not delivery.delta.crosses_zero()
    assert (delivery.fixed, delivery.broke) == (139, 61)


def test_the_strict_bar_stays_unreachable():
    """Reported because it did not move: pass@>=4 is flat under the largest
    intervention in the project."""
    c = D.wixqa_comparison("rag-wider-context", "rag-better-retriever", bar=4)
    assert c.delta.point_estimate == pytest.approx(0.000, abs=TOLERANCE)
    assert c.wilson_a.point == pytest.approx(0.007, abs=TOLERANCE)


# --------------------------------------------------------------------------
# O6 -- the loop on top of retrieval
# --------------------------------------------------------------------------


def test_self_refinement_does_not_compound_with_retrieval():
    c = D.wixqa_loop_comparison()
    assert c.wilson_b.point == pytest.approx(0.571, abs=TOLERANCE)
    assert c.wilson_a.point == pytest.approx(0.556, abs=TOLERANCE)
    assert c.delta.point_estimate == pytest.approx(-0.015, abs=TOLERANCE)
    assert c.delta.crosses_zero()


def test_the_loop_study_uses_the_right_comparator():
    """Regression guard for a real mistake caught while reviewing a figure.

    `pilots/4-rag-wider-context-goldonly` is a separate earlier pilot sitting
    four points lower; pairing the refinement run against it turns the
    published -0.015 into a +0.045 and reverses the study's conclusion. The
    comparator must be the seed-42 gold-retrieved slice of the full run.
    """
    wrong = D.wixqa_pass_rate("pilots/4-rag-wider-context-goldonly")
    right = D.wixqa_loop_comparison().wilson_b
    assert wrong.point == pytest.approx(0.511, abs=TOLERANCE)
    assert right.point == pytest.approx(0.571, abs=TOLERANCE)


def test_refinement_helps_weak_answers_and_taxes_good_ones():
    buckets = D.wixqa_loop_by_prior_score()
    assert buckets[0]["mean_delta"] > 0.3
    assert buckets[1]["mean_delta"] > 0.3
    assert buckets[3]["mean_delta"] == pytest.approx(-0.11, abs=0.01)
    assert buckets[3]["worsened"] == 7 and buckets[3]["improved"] == 0


def test_a_perfect_gate_would_help_and_the_model_is_not_one():
    policies = D.wixqa_loop_policy_ladder()
    single = policies["single pass, never refine"].point
    assert policies["refine only weak answers (oracle)"].point == pytest.approx(
        single + 0.038, abs=0.002
    )
    assert policies["refine when the model says it is not done"].point == pytest.approx(
        single, abs=TOLERANCE
    )
    said_complete, total = D.wixqa_self_assessment_rate()
    assert said_complete / total == pytest.approx(0.59, abs=0.01)


# --------------------------------------------------------------------------
# O7 / offline evidence
# --------------------------------------------------------------------------


def test_fine_tuning_hurts():
    lora = D.lora_result()
    assert lora["delta"] == pytest.approx(-0.292, abs=TOLERANCE)
    assert lora["ci"][1] < 0


def test_retriever_ladder_ordering_and_honest_negatives():
    ladder = D.retriever_ladder()
    at3 = {k: v["hitrate"]["3"] for k, v in ladder.items() if k != "_meta"}
    assert max(at3, key=at3.get) == "bge_chunk"
    assert at3["bge_chunk"] == pytest.approx(0.665, abs=TOLERANCE)
    assert at3["bm25"] < at3["minilm_whole"]  # lexical alone loses
    assert at3["hybrid_rrf"] < at3["bge_chunk"]  # fusion drags the strong retriever down


def test_grounding_window_coverage_ladder():
    cov = D.coverage_ladder()
    assert cov["head900"]["coverage_gold_mean"] == pytest.approx(0.412, abs=TOLERANCE)
    assert cov["chunk2400"]["coverage_gold_mean"] == pytest.approx(0.655, abs=TOLERANCE)
    ceiling = cov["_meta"]["ceiling_full_gold_article_coverage"]
    assert cov["chunk2400"]["coverage_gold_mean"] < ceiling  # never claim above the ceiling


def test_extraction_ratio_is_reported_as_a_worsening():
    printout = D.analysis_printout("rag-wixqa/wider-context-vs-narrow.txt")
    assert printout["extraction_before"] == pytest.approx(0.88, abs=0.005)
    assert printout["extraction_after"] == pytest.approx(0.61, abs=0.005)
    assert printout["extraction_after"] < printout["extraction_before"]


# --------------------------------------------------------------------------
# O2 -- the retired result, against its own logs
# --------------------------------------------------------------------------


def test_the_retracted_headline_does_not_match_its_log():
    rows = D.v1_claim_vs_log()
    pass_rate_row = next(r for r in rows if "25%" in r["claim"])
    assert "0.33" in pass_rate_row["logged"] and "0.84" in pass_rate_row["logged"]


def test_the_hundred_percent_was_the_store_returning_its_own_answer_key():
    same_q = next(
        r for r in D.v1_phase_summaries("phase6") if "Same" in r.get("experiment_id", "")
    )
    assert same_q["pass_rate"] == 1.0
    assert same_q["memory_hit_rate"] == 1.0


def test_the_memory_comparison_was_published_with_the_sign_reversed():
    rates = {
        r["experiment_id"]: r["pass_rate"] for r in D.v1_phase_summaries("phase1")
    }
    with_memory = next(v for k, v in rates.items() if "WithMemory" in k)
    no_memory = next(v for k, v in rates.items() if "NoMemory" in k)
    assert no_memory > with_memory  # the document claimed the opposite


def test_the_temperature_grid_was_never_fully_run():
    temps = {r["config_used"]["student_temp"] for r in D.v1_phase_summaries("phase3")}
    assert temps == {0.0, 0.2}  # the write-up compared 0.0 / 0.3 / 0.5


def test_the_pass_rate_was_a_function_of_a_dial_the_experimenter_set():
    """The sharpest row in the retraction, and the only table in the retired
    write-up that reconciles against its logs exactly: the same runs score
    0.975, 0.775 or 0.338 depending purely on the threshold chosen."""
    sweep = {round(t, 2): r for t, r, _n in D.v1_pass_threshold_sweep()}
    assert sweep[0.75] == pytest.approx(0.975, abs=TOLERANCE)
    assert sweep[0.80] == pytest.approx(0.775, abs=TOLERANCE)
    assert sweep[0.85] == pytest.approx(0.337, abs=TOLERANCE)
    assert sweep[0.75] - sweep[0.85] > 0.6  # the dial is worth more than any result reported


def test_the_teacher_style_comparison_was_overstated_and_later_overturned():
    """The old run picked ORCA as the house style on a 90/85/80 comparison.
    The logs say 90/50/40, and a later powered re-test found ORCA
    indistinguishable from a minimal prompt."""
    styles = dict(D.v1_feedback_styles())
    assert styles["ORCA"] == pytest.approx(0.90, abs=0.005)
    assert styles["principle"] == pytest.approx(0.50, abs=0.005)
    assert styles["chain-of-thought"] == pytest.approx(0.40, abs=0.005)


def test_every_retired_phase_is_accounted_for():
    phases = {row["phase"] for row in D.v1_phase_table()}
    assert phases == {f"phase{i}" for i in range(7)}


def test_v1_metric_weighted_resemblance_over_correctness():
    weights = D.v1_metric_weights()
    assert sum(weights.values()) == pytest.approx(1.0)
    reference_weighted = sum(w for k, w in weights.items() if "blind" not in k)
    assert reference_weighted == pytest.approx(0.70)


# --------------------------------------------------------------------------
# the stages before and around the experiments
# --------------------------------------------------------------------------


def test_dataset_cleaning_totals():
    """12,428 raw pairs -> 10,024 clean, across seven source domains."""
    reports = D.cleaning_reports()
    assert sum(r["before"]["n"] for r in reports.values()) == 12428
    assert sum(r["after"]["n"] for r in reports.values()) == 10024
    assert len(reports) == 7


def test_the_split_the_experiments_used_was_assessed_ready():
    scores = D.readiness("rag")
    assert scores["overall"] == pytest.approx(93.4, abs=0.05)
    assert scores["verdict"] == "READY"
    assert scores["n"] == 631


def test_both_candidate_judges_failed_calibration():
    """Reported as a result: the instrument did not pass its own probe, and
    the protocol changed rather than the probe."""
    probes = D.judge_calibration()
    assert probes, "no full-size probes found"
    assert not any(p["passed_gate"] for p in probes)
    # the decisive column: a judge that waves through deliberately-wrong answers
    assert max(p["plausible_wrong"] for p in probes) > 0.5


def test_the_lower_pass_bar_leaves_no_headroom():
    """Why the headline uses 'correct AND complete'."""
    sensitivity = D.track_a_bar_sensitivity()
    assert all(v[3] > 0.97 for v in sensitivity.values())  # everything passes at the lower bar
    assert sensitivity["1-baseline"][4] == pytest.approx(0.821, abs=TOLERANCE)


def test_chunking_beats_a_better_encoder():
    levers = D.retriever_levers()
    assert levers["splitting articles into chunks"] == pytest.approx(0.095, abs=TOLERANCE)
    assert levers["a stronger encoder"] == pytest.approx(0.070, abs=TOLERANCE)
    assert levers["splitting articles into chunks"] > levers["a stronger encoder"]


def test_selective_retrieval_oracle_matches_the_report():
    """docs/EXPERIMENT_RESULTS.md §7.2 publishes 0.920, an oracle gating each attempt."""
    oracle = D.selective_oracle("rag-medquad", "small-model-with-rag", "small-model-no-rag")
    assert oracle["gate per attempt (the absolute ceiling)"] == pytest.approx(0.920, abs=TOLERANCE)
    assert oracle["baseline"] == pytest.approx(0.821, abs=TOLERANCE)
    # the buildable gate is worth less than the ceiling, and both beat always-on
    assert (
        oracle["always apply"]
        < oracle["gate per question (the buildable target)"]
        < oracle["gate per attempt (the absolute ceiling)"]
    )


def test_retrieval_trades_diversity_for_consistency():
    """Retrieval raises per-attempt accuracy and lowers the chance that at
    least one of several attempts lands -- opposite directions, same runs.
    Published as 0.606 -> 0.640 and 0.89 -> 0.74."""
    metrics = D.reliability_metrics()
    base, rag = metrics["no-rag"], metrics["with-rag"]
    assert base["per_attempt"] == pytest.approx(0.606, abs=TOLERANCE)
    assert rag["per_attempt"] == pytest.approx(0.640, abs=TOLERANCE)
    assert base["ever_right"] == pytest.approx(0.89, abs=0.005)
    assert rag["ever_right"] == pytest.approx(0.74, abs=0.005)
    assert rag["per_attempt"] > base["per_attempt"] and rag["ever_right"] < base["ever_right"]


def test_the_unfinished_sweep_is_never_pooled_with_the_published_set():
    """A larger reliability sweep exists under the same study directory but was
    judged with a different model. Pooling it would move the published
    difference by tens of points, so the default must not reach it."""
    published = D.reliability_metrics()
    other = D.reliability_metrics("rag-medquad-reliability")
    assert published["no-rag"]["questions"] == 35
    assert other["no-rag"]["questions"] == 125
    assert abs(other["with-rag"]["per_attempt"] - published["with-rag"]["per_attempt"]) > 0.3


def test_faithfulness_aggregates_every_seed():
    """Regression guard. This function used to return the first run it found
    with a value, and because run directories sort lexically that was seed123
    alone -- one third of the evidence reported as if it were all of it, at
    0.828 / 58% instead of the published 0.809 / 61%."""
    faith = D.faithfulness("rag-medquad", "small-model-with-rag")
    assert faith is not None
    assert faith["seeds"] == 3
    assert faith["parsed"] + faith["null"] == 375
    assert faith["mean"] == pytest.approx(0.809, abs=0.002)
    assert faith["null_rate"] == pytest.approx(0.608, abs=0.002)


def test_both_calibration_probe_formats_are_read():
    """Regression guard. The two candidate judges were probed by different
    script versions writing different key names; reading only one shape
    dropped the local judge entirely while the caption still said 'neither
    candidate passed'."""
    judges = {p["judge"] for p in D.judge_calibration()}
    assert len(judges) >= 2, f"only one candidate judge was read: {judges}"
    assert any("ollama" in j or "local" in j for j in judges)
    assert any("groq" in j for j in judges)


def test_retrieval_makes_gap_answers_dependable():
    """The product-shaped result, on the 13 questions the model never once got
    right unaided: published as 0/13 -> 4/13 reliably correct."""
    gaps = D.reliability_on_genuine_gaps()
    base, rag = gaps["no-rag"], gaps["with-rag"]
    assert base["questions"] == 13
    assert base["always_right_count"] == 0
    assert rag["always_right_count"] == 4
    assert base["per_attempt"] == pytest.approx(0.231, abs=TOLERANCE)
    assert rag["per_attempt"] == pytest.approx(0.354, abs=TOLERANCE)


# --------------------------------------------------------------------------
# citations
# --------------------------------------------------------------------------


def test_documented_counts_match_what_is_actually_there():
    """Four countable claims went stale the moment the thing they counted
    changed: the test count, the number of decisions, the number of guardrails
    that fired, and a rounded threshold. Each is now derived, and this pins
    the derivations so a hand-typed count cannot creep back in."""
    decisions = D.decision_log()
    tab20 = (D.ROOT / "reports" / "tables" / "tab-20-decision-log.md").read_text(encoding="utf-8")
    assert f"{len(decisions)} decisions" in tab20, (
        "the decision count in the note is not derived from the log"
    )
    assert tab20.startswith("**Table 20**"), "APA 7 label missing from the table"

    live = D.test_count()
    for doc in ("README.md", "docs/EXPERIMENT_RESULTS.md"):
        text = (D.ROOT / doc).read_text(encoding="utf-8")
        stated = re.findall(r"(\d{3}) tests", text)
        assert stated, f"{doc}: no test count stated"
        for value in stated:
            assert int(value) == live, (
                f"{doc} says {value} tests; the suite collects {live}"
            )


def test_gold_articles_were_mostly_truncated():
    """The two numbers behind the delivery finding, recomputed rather than
    quoted — they used to sit in a caption citing a file that did not contain
    them. Counted per article (177 across 133 questions), which is what the
    published median of 3,555 is a statement about.

    This one needs the WixQA knowledge base, which is third-party data (MIT,
    50 MB) that a clone acquires with `scripts/dataset/fetch_wixqa.py` rather
    than carries. Absent, the test skips; present but unreadable, it fails —
    the distinction structure.md §E asks for between "a fresh clone lacks it"
    and "the layout moved".
    """
    kb = D.ROOT / "data" / "external" / "wixqa" / "kb_corpus.jsonl"
    if not (D.ROOT / "data" / "external" / "wixqa").is_dir():
        pytest.skip("WixQA knowledge base not fetched; run scripts/dataset/fetch_wixqa.py")
    assert kb.is_file(), f"the WixQA directory exists but {kb.name} is missing — layout moved?"

    trunc = D.gold_article_truncation()
    assert trunc["n_articles"] == 177
    assert trunc["median_chars"] == 3555
    assert 0.92 < trunc["share_truncated"] < 0.93


def test_every_citation_in_the_report_resolves():
    """The report cites references by number against one generated list. A
    citation pointing past the end of that list would look authoritative and
    resolve to nothing."""
    import re

    report = (D.ROOT / "docs" / "EXPERIMENT_RESULTS.md").read_text(encoding="utf-8")
    cited = {int(n) for n in re.findall(r"\[(\d+)\]\(#references\)", report)}
    available = len(D.literature())
    assert cited, "the report cites nothing"
    assert max(cited) <= available, (
        f"citation [{max(cited)}] has no reference — only {available} exist"
    )
    assert min(cited) >= 1


def test_the_bibliography_is_complete_enough_to_cite():
    """Every entry needs the fields a reader would use to find the work."""
    for work in D.literature():
        for field in ("authors", "year", "title", "venue", "id", "tested", "verdict"):
            assert work.get(field), f"{work['key']}: missing {field}"
        assert work["year"].isdigit() and 1900 < int(work["year"]) < 2100


def test_the_contradicted_finding_is_still_labelled_as_such():
    """One published method did not transfer at this scale. If that row ever
    quietly becomes 'confirmed', the most interesting result in the comparison
    has been smoothed away."""
    works = {w["key"]: w for w in D.literature()}
    assert "contradicted" in works["madaan2023"]["verdict"]
    assert "confirmed" in works["huang2024"]["verdict"]


# --------------------------------------------------------------------------
# layout
# --------------------------------------------------------------------------


def test_evidence_layout_has_not_moved():
    """A moved study directory must fail here rather than quietly produce an
    empty figure. The module-level skip covers the fresh-clone case; this
    covers the case where `runs/` exists but the layout drifted."""
    for study in ("teaching-loop-medquad", "rag-medquad", "rag-medquad-fair-tests"):
        assert D.study_runs(study), f"no runs discovered under runs/{study}"
    for step in D.WIXQA_STEPS:
        assert D.wixqa_records(step), f"no judged records for WixQA step {step}"


def test_pilots_cannot_leak_into_a_headline():
    """`discover_runs` scans one level, so a pilot sitting in `pilots/` is
    structurally unreachable from a study comparison -- the guarantee that
    replaced a filter someone had to remember to apply."""
    conditions = D.study_runs("teaching-loop-medquad")
    assert not any("pilot" in c for c in conditions)
    for condition in conditions:
        n = D.study_pass_rate("teaching-loop-medquad", condition).n
        # 125 held-out questions x 3 seeds -- except the arm deliberately given
        # the answer key, where the leakage guard aborted one seed's run. That
        # short count is the guard working and is labelled wherever it appears.
        expected = 250 if condition == "4-teacher-sees-answer" else 375
        assert n == expected, f"{condition}: expected {expected} question-runs, found {n}"

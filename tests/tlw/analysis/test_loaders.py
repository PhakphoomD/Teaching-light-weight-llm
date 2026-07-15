"""Loader tests (T2.8 step 1): discovery, parsing, V8 no-conflation guard.

Synthetic fixtures (`make_run`) are the primary vehicle. The real n=5
dry-run artifacts under `runs/trackA_p2_arm{A,C}_diabetes__seed42__*` are
used for one shapes-only smoke test (`test_discover_runs_on_real_dry_run_artifacts`)
-- read-only, never modified."""

from pathlib import Path

import pytest

from src.tlw.analysis.loaders import (
    ConflationError,
    assert_single_memory_type,
    build_cluster_table,
    discover_runs,
    final_passes_by_question,
    group_runs,
    group_runs_by_arm_seed_preset_memory,
    load_run,
    load_rounds,
    select_arm_runs,
)

REAL_RUNS_DIR = Path(__file__).resolve().parents[3] / "runs"


# --- discovery / parsing -----------------------------------------------------------


def test_discover_runs_finds_synthetic_dirs(runs_root, make_run):
    make_run("armA__seed42", arm="A", seed=42, passed_flags=[True, False, True])
    make_run("armB__seed42", arm="B", seed=42, passed_flags=[False, True, True])

    runs = discover_runs(runs_root)
    assert {r.run_id for r in runs} == {"armA__seed42", "armB__seed42"}


def test_discover_runs_skips_non_run_directories(runs_root, make_run):
    make_run("armA__seed42", arm="A", seed=42, passed_flags=[True])
    (runs_root / "calibration").mkdir()  # no summary.jsonl -- not a run
    (runs_root / "calibration" / "notes.txt").write_text("x", encoding="utf-8")

    runs = discover_runs(runs_root)
    assert [r.run_id for r in runs] == ["armA__seed42"]


def test_discover_runs_empty_dir_returns_empty_list(tmp_path):
    assert discover_runs(tmp_path / "does_not_exist") == []


def test_run_record_properties_match_written_config(runs_root, make_run):
    make_run("armC__seed13", arm="C", seed=13, memory_type="none", passed_flags=[True, True])
    run = load_run(runs_root / "armC__seed13")
    assert run.arm == "C"
    assert run.seed == 13
    assert run.memory_type == "none"
    assert run.preset_student == "minimal"
    assert run.preset_teacher == "orca"
    assert run.student_model == "qwen2.5:7b-instruct"
    assert run.num_questions == 2
    assert run.passed_count == 2
    assert run.pass_rate == pytest.approx(1.0)
    assert run.group_key() == ("C", "none")


def test_load_run_missing_summary_raises(tmp_path):
    empty_dir = tmp_path / "broken_run"
    empty_dir.mkdir()
    with pytest.raises(FileNotFoundError):
        load_run(empty_dir)


def test_load_rounds_reads_all_rows(runs_root, make_run):
    make_run("armA__seed42", arm="A", seed=42, passed_flags=[True, False])
    rounds = load_rounds(runs_root / "armA__seed42")
    assert len(rounds) == 2
    assert {r["question_id"] for r in rounds} == {"diabetes-00000", "diabetes-00001"}


def test_load_rounds_missing_file_returns_empty(tmp_path):
    d = tmp_path / "no_rounds"
    d.mkdir()
    assert load_rounds(d) == []


# --- grouping ---------------------------------------------------------------------


def test_group_runs_separates_memory_types(runs_root, make_run):
    make_run("armC_none__seed42", arm="C", seed=42, memory_type="none", passed_flags=[True])
    make_run("armC_faiss__seed42", arm="C", seed=42, memory_type="faiss", passed_flags=[True])
    runs = discover_runs(runs_root)
    groups = group_runs(runs)
    assert set(groups.keys()) == {("C", "none"), ("C", "faiss")}
    assert len(groups[("C", "none")]) == 1
    assert len(groups[("C", "faiss")]) == 1


def test_group_runs_by_arm_seed_preset_memory(runs_root, make_run):
    make_run("armB__seed42", arm="B", seed=42, passed_flags=[True])
    make_run("armB__seed13", arm="B", seed=13, passed_flags=[True])
    runs = discover_runs(runs_root)
    groups = group_runs_by_arm_seed_preset_memory(runs)
    keys = {(k[0], k[1]) for k in groups}
    assert keys == {("B", 42), ("B", 13)}


def test_select_arm_runs_filters_by_arm_and_memory(runs_root, make_run):
    make_run("armC_none", arm="C", seed=42, memory_type="none", passed_flags=[True])
    make_run("armC_faiss", arm="C", seed=42, memory_type="faiss", passed_flags=[True])
    make_run("armB_none", arm="B", seed=42, memory_type="none", passed_flags=[True])
    runs = discover_runs(runs_root)

    only_c_none = select_arm_runs(runs, "C", "none")
    assert [r.run_id for r in only_c_none] == ["armC_none"]


# --- V8 no-conflation guard -----------------------------------------------------


def test_assert_single_memory_type_passes_when_uniform(runs_root, make_run):
    make_run("r1", arm="C", seed=42, memory_type="none", passed_flags=[True])
    make_run("r2", arm="C", seed=13, memory_type="none", passed_flags=[True])
    runs = discover_runs(runs_root)
    assert assert_single_memory_type(runs) == "none"


def test_assert_single_memory_type_raises_on_mixed_memory(runs_root, make_run):
    make_run("r1", arm="C", seed=42, memory_type="none", passed_flags=[True])
    make_run("r2", arm="C", seed=42, memory_type="faiss", passed_flags=[True])
    runs = discover_runs(runs_root)
    with pytest.raises(ConflationError, match="V8"):
        assert_single_memory_type(runs)


def test_assert_single_memory_type_raises_on_empty():
    with pytest.raises(ConflationError):
        assert_single_memory_type([])


# --- final-round / cluster table -------------------------------------------------


def test_final_passes_by_question_takes_last_round(runs_root, make_run):
    make_run(
        "armC__seed42",
        arm="C",
        seed=42,
        passed_flags=[True, False],
        rounds_per_question=[3, 2],
    )
    rounds = load_rounds(runs_root / "armC__seed42")
    finals = final_passes_by_question(rounds)
    assert finals["diabetes-00000"] is True
    assert finals["diabetes-00001"] is False
    # every question contributes exactly one final verdict, not one per round
    assert len(finals) == 2


def test_build_cluster_table_pools_seeds_within_question(runs_root, make_run):
    make_run(
        "armC__seed42",
        arm="C",
        seed=42,
        memory_type="none",
        passed_flags=[True, False],
        question_ids=["q0", "q1"],
    )
    make_run(
        "armC__seed13",
        arm="C",
        seed=13,
        memory_type="none",
        passed_flags=[False, False],
        question_ids=["q0", "q1"],
    )
    make_run(
        "armB__seed42",
        arm="B",
        seed=42,
        memory_type="none",
        passed_flags=[False, True],
        question_ids=["q0", "q1"],
    )
    runs = discover_runs(runs_root)
    runs_by_arm = {
        "C": select_arm_runs(runs, "C", "none"),
        "B": select_arm_runs(runs, "B", "none"),
    }
    cluster_table, seed_index = build_cluster_table(runs_by_arm)

    # discover_runs globs directories in sorted order, so seed13 precedes
    # seed42 here (lexical sort of "armC__seed13" < "armC__seed42").
    assert sorted(cluster_table["q0"]["C"]) == sorted([True, False])  # seed42, seed13 pooled
    assert cluster_table["q0"]["B"] == [False]
    assert sorted(seed_index["q0"]["C"]) == [13, 42]
    assert seed_index["q0"]["B"] == [42]


# --- real dry-run artifacts (shapes only) ----------------------------------------


@pytest.mark.skipif(not REAL_RUNS_DIR.is_dir(), reason="runs/ not present in this checkout")
def test_discover_runs_on_real_dry_run_artifacts():
    """Shapes-only smoke test against the REAL n=5 dry-run artifacts
    (`runs/trackA_p2_arm{A,C}_diabetes__seed42__*`, read-only -- this test
    must never write into `runs/`). Skips cleanly if a concurrent pilot
    agent has not left those specific dirs in this checkout."""
    real_dirs = [
        p for p in REAL_RUNS_DIR.glob("trackA_p2_arm*_diabetes__seed42__*") if (p / "summary.jsonl").is_file()
    ]
    if not real_dirs:
        pytest.skip("no matching real dry-run artifacts found under runs/")

    runs = discover_runs(REAL_RUNS_DIR, pattern="trackA_p2_arm*_diabetes__seed42__*")
    assert len(runs) >= 1
    for run in runs:
        assert run.arm in {"A", "B", "C", "D"}
        assert run.memory_type in {"none", "faiss", "rag"}
        assert isinstance(run.seed, int)
        assert run.num_questions >= 1
        rounds = load_rounds(run.path)
        assert len(rounds) >= run.num_questions  # >= because multi-round arms have >1 row/question
        for row in rounds:
            assert "question_id" in row
            assert "passed" in row
            assert "score" in row

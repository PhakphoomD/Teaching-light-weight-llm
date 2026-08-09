"""T3.4 RAG ablation report tests (rag-medquad-protocol §4/§6).

Uses the shared synthetic-run factory (`make_run`) to build {3B, 3B+RAG, 7B,
7B+RAG} runs and checks: label derivation, the pre-registered 3B+RAG - 3B delta
(same machinery as Track A), and the three-separate-columns rule (correctness /
faithfulness / reference_match, never merged).
"""

from src.tlw.analysis.loaders import discover_runs
from src.tlw.analysis.rag_report import (
    build_rag_report,
    group_by_rag_label,
    rag_label,
)


def _mk(make_run, name, model, mem, passed, seed, faith=None, filtered=0):
    qids = [f"diabetes-{i:05d}" for i in range(len(passed))]
    return make_run(
        name, arm="A", seed=seed, memory_type=mem, student_model=model,
        passed_flags=passed, question_ids=qids,
        memory_used_flags=[mem == "rag"] * len(passed),
        faithfulness_mean=faith, grounding_filtered=filtered,
    )


def test_rag_label_derivation(make_run):
    r3b = _mk(make_run, "a", "qwen2.5:3b", "none", [True], 42)
    r3brag = _mk(make_run, "b", "qwen2.5:3b", "rag", [True], 42)
    r7b = _mk(make_run, "c", "qwen2.5:7b-instruct", "none", [True], 42)
    from src.tlw.analysis.loaders import load_run
    assert rag_label(load_run(r3b)) == "3B"
    assert rag_label(load_run(r3brag)) == "3B+RAG"
    assert rag_label(load_run(r7b)) == "7B"


def test_headline_delta_3brag_minus_3b(make_run, runs_root):
    # 3B baseline: 2/5 pass; 3B+RAG: 4/5 pass (RAG helps by +0.4 here), 3 seeds.
    for seed in (13, 42, 123):
        _mk(make_run, f"3b_{seed}", "qwen2.5:3b", "none",
            [True, True, False, False, False], seed, filtered=0)
        _mk(make_run, f"3brag_{seed}", "qwen2.5:3b", "rag",
            [True, True, True, True, False], seed, faith=0.8, filtered=1)

    runs = discover_runs(runs_root)
    report = build_rag_report(runs, n_resamples=500, seed=0)

    assert set(report["labels_present"]) >= {"3B", "3B+RAG"}
    headline = report["comparisons"]["3B+RAG - 3B"]
    # pass_rate(3B+RAG)=0.8, pass_rate(3B)=0.4 -> delta ~ +0.4
    assert abs(headline.bootstrap.point_estimate - 0.4) < 1e-6
    # descriptive Wilson present for both labels
    assert "3B" in report["descriptive"] and "3B+RAG" in report["descriptive"]


def test_three_columns_never_merged(make_run, runs_root):
    _mk(make_run, "3brag_42", "qwen2.5:3b", "rag", [True, True, False], 42, faith=0.9, filtered=2)
    runs = discover_runs(runs_root)
    report = build_rag_report(runs, n_resamples=200, seed=0)

    # correctness (from reference_match table) and faithfulness live in SEPARATE
    # structures — never combined into a single score.
    assert report["reference_match"]["3B+RAG"]["correctness_pass_rate"] is not None
    assert report["faithfulness"]["3B+RAG"]["faithfulness_mean"] == 0.9
    assert report["grounding_filtered"]["3B+RAG"] == 2
    # the 'none'-memory label would carry no faithfulness
    assert "3B+RAG" in report["faithfulness"]


def test_missing_arm_ignored(make_run):
    # A non-A run (e.g. a stray Track-A arm C) must not pollute the RAG grouping.
    make_run("armC", arm="C", seed=42, memory_type="none",
             student_model="qwen2.5:3b", passed_flags=[True])
    ragrun = _mk(make_run, "3brag", "qwen2.5:3b", "rag", [True], 42, faith=0.7)
    from src.tlw.analysis.loaders import load_run
    grouped = group_by_rag_label([load_run(ragrun.parent / "armC"), load_run(ragrun)])
    assert "3B+RAG" in grouped and all(lbl != "3B" for lbl in grouped)  # armC dropped

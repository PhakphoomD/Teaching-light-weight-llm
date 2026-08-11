"""CLI tests (build instruction 4): the demo invocation + the banner
must actually reach stdout, and correctness/reference_match must print as
separate lines."""

from src.tlw.analysis.cli import main


def test_cli_prints_not_pre_registered_banner_for_pilot_data(runs_root, make_run, capsys):
    for seed in (13, 42, 123):
        make_run(f"armA__seed{seed}", arm="A", seed=seed, memory_type="none", passed_flags=[True, False, True])
        make_run(f"armB__seed{seed}", arm="B", seed=seed, memory_type="none", passed_flags=[True, True, False])
        make_run(f"armC__seed{seed}", arm="C", seed=seed, memory_type="none", passed_flags=[True, True, True])

    exit_code = main(["--runs-dir", str(runs_root), "--comparison", "C-B", "--resamples", "500", "--seed", "0"])
    out = capsys.readouterr().out

    assert exit_code == 0
    assert "NOT the pre-registered sample" in out
    assert "correctness (HEADLINE) vs reference_match (DIAGNOSTIC ONLY" in out


def test_cli_marks_arm_d_as_leakage_ceiling_not_a_result(runs_root, make_run, capsys):
    make_run("armC__seed42", arm="C", seed=42, memory_type="none", passed_flags=[True, False])
    make_run("armD__seed42", arm="D", seed=42, memory_type="none", passed_flags=[True, True])

    exit_code = main(["--runs-dir", str(runs_root), "--comparison", "D-C", "--resamples", "500", "--seed", "0"])
    out = capsys.readouterr().out

    assert exit_code == 0
    assert "LEAKAGE CEILING -- not a claimed result" in out


def test_cli_no_runs_found_exits_nonzero(tmp_path, capsys):
    exit_code = main(["--runs-dir", str(tmp_path / "empty")])
    err = capsys.readouterr().err
    assert exit_code == 1
    assert "No runs found" in err


def test_cli_refuses_mixed_memory_via_v8(runs_root, make_run, capsys):
    """Even though the CLI filters by --memory-type, exercise the refusal
    path directly through a hand-mixed report build is covered in
    test_report.py; here we confirm the CLI's normal (single memory type)
    path never trips the guard for a clean headline set."""
    make_run("armC__seed42", arm="C", seed=42, memory_type="none", passed_flags=[True])
    make_run("armB__seed42", arm="B", seed=42, memory_type="none", passed_flags=[False])

    exit_code = main(
        ["--runs-dir", str(runs_root), "--comparison", "C-B", "--memory-type", "none", "--resamples", "200"]
    )
    assert exit_code == 0


def test_cli_default_comparisons_include_headline_c_minus_b(runs_root, make_run, capsys):
    for arm, flags in (("A", [True, False]), ("B", [True, True]), ("C", [False, True]), ("D", [True, True])):
        make_run(f"arm{arm}__seed42", arm=arm, seed=42, memory_type="none", passed_flags=flags)

    exit_code = main(["--runs-dir", str(runs_root), "--resamples", "200"])
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "C-B" in out
    assert "B-A" in out
    assert "D-C" in out

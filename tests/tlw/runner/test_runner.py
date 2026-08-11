"""Tests for the runner: config->blocks composition (mocked, no API),
run_id format, summary-shape round-trip vs schema.md, CLI arg handling, and
the strangler "local"-provider override behavior.

No real network/API calls anywhere in this file — the student/teacher/judge
clients are monkeypatched to a local MockClient, mirroring the pattern
already established in tests/tlw/loop/conftest.py.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

import pytest
import yaml

import src.tlw.runner as runner
from src.tlw.config.loader import load_config
from src.tlw.config.schema import EvalSlot, ExperimentConfig, MemorySlot, ModelSlot, ParamsSlot, PresetSlot
from src.tlw.registries import MEMORY_REGISTRY  # noqa: F401  ensures block registration happened


class MockClient:
    """Same shape as tests/tlw/loop/conftest.py::MockClient, plus a `usage`
    field on the returned result so _TokenCounter has something real to sum."""

    def __init__(self, responses: Optional[List[str]] = None, tokens_per_call: int = 10):
        self._responses = list(responses or [])
        self._tokens_per_call = tokens_per_call
        self.calls: List[Dict[str, Any]] = []

    def name(self) -> str:
        return "mock:client"

    def chat(self, messages, temperature=0.0, max_tokens=256, timeout_s=60):
        self.calls.append({"messages": messages, "temperature": temperature, "max_tokens": max_tokens})
        text = self._responses.pop(0) if self._responses else '{"score": 4, "reason": "ok"}'
        usage = SimpleNamespace(total_tokens=self._tokens_per_call)
        return SimpleNamespace(text=text, error=None, usage=usage)


ARM_A_OVERRIDE = {"params": {"arm": "A", "seed": 42}}
ARM_C_OVERRIDE = {"params": {"arm": "C", "seed": 42}}


def write_yaml(path: Path, data: Dict[str, Any]) -> Path:
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


@pytest.fixture
def tiny_dataset(tmp_path):
    ds = tmp_path / "tiny.jsonl"
    ds.write_text(
        "\n".join(
            [
                '{"id": "d-0", "domain": "diabetes", "question": "What is X?", "answer": "X is the reference answer."}',
                '{"id": "d-1", "domain": "diabetes", "question": "What is Y?", "answer": "Y is the other reference."}',
            ]
        ),
        encoding="utf-8",
    )
    return ds


def _cfg(arm: str, seed: int = 42, memory_type: str = "none") -> ExperimentConfig:
    model_kwargs = dict(temperature=0.3, max_tokens=64, timeout=30)
    return ExperimentConfig(
        student=ModelSlot(provider="local", model="qwen2.5:7b-instruct", **model_kwargs),
        teacher=ModelSlot(provider="groq", model="qwen/qwen3-32b", **model_kwargs),
        preset=PresetSlot(student="minimal", teacher="orca"),
        memory=MemorySlot(type=memory_type),
        params=ParamsSlot(seed=seed, arm=arm, max_rounds=2),
        eval=EvalSlot(
            judge=ModelSlot(provider="local", model="llama3.1:8b", **model_kwargs),
            mode="blind",
            pass_threshold=0.75,
            weights={"blind_score": 1.0},
        ),
        _merged={"params": {"arm": arm, "seed": seed}},
    )


# --- run_id -------------------------------------------------------------


def test_make_run_id_format():
    fixed = datetime(2026, 7, 13, 14, 57, 21, tzinfo=timezone.utc)
    run_id = runner.make_run_id(Path("experiments/trackA_p2_armC_diabetes.yml"), 42, now=fixed)
    assert run_id == "trackA_p2_armC_diabetes__seed42__20260713T145721Z"


def test_make_run_id_encodes_arm_and_seed_distinctly():
    """A headline (memory-off) and a C'/D' memory-on run must never collide
    in run_id even at the same timestamp/seed, because the config STEM
    (which names the arm/variant) is part of the id (schema.md Memory v2 §5)."""
    fixed = datetime(2026, 1, 1, tzinfo=timezone.utc)
    a = runner.make_run_id(Path("experiments/trackA_p2_armC_diabetes.yml"), 42, now=fixed)
    b = runner.make_run_id(Path("experiments/trackA_p2_armCprime_diabetes.yml"), 42, now=fixed)
    assert a != b


# --- dataset loading ------------------------------------------------------


def test_load_dataset_reads_jsonl(tiny_dataset):
    records = runner.load_dataset(tiny_dataset)
    assert len(records) == 2
    assert records[0]["id"] == "d-0"


def test_load_dataset_limit_is_deterministic_prefix(tiny_dataset):
    one = runner.load_dataset(tiny_dataset, limit=1)
    assert len(one) == 1
    assert one[0]["id"] == "d-0"  # first record, not sampled


def test_load_dataset_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        runner.load_dataset(tmp_path / "nope.jsonl")


# --- _build_params: ground_truth only for arm D --------------------------


def test_build_params_ground_truth_only_for_arm_d():
    params_a = runner._build_params(_cfg("A"), "run-1", ground_truth="the answer")
    params_c = runner._build_params(_cfg("C"), "run-1", ground_truth="the answer")
    params_d = runner._build_params(_cfg("D"), "run-1", ground_truth="the answer")
    assert "ground_truth" not in params_a
    assert "ground_truth" not in params_c
    assert params_d["ground_truth"] == "the answer"


def test_build_params_carries_run_identity():
    params = runner._build_params(_cfg("C", seed=7), "my-run-id", ground_truth=None)
    assert params["run_id"] == "my-run-id"
    assert params["seed"] == 7
    assert params["teacher_model"] == "qwen/qwen3-32b"


# --- _diagnose_round: reference_match is legal for every arm -------------


def test_diagnose_round_computed_even_without_params_ground_truth():
    """The runner computes reference_match post-hoc from the dataset's own
    ground truth for ALL arms (teaching-loop-protocol §2, legal score-path use) even
    though arm A/B/C never receive ground_truth inside params (previous
    test) — the two paths are intentionally decoupled."""
    round_record = {"answer": "X is the reference answer."}
    diag = runner._diagnose_round(round_record, "X is the reference answer.")
    assert diag is not None
    assert diag["semantic_sim"] > 0.9  # near-identical text
    assert "rouge_l" in diag


def test_diagnose_round_none_without_ground_truth():
    assert runner._diagnose_round({"answer": "anything"}, None) is None
    assert runner._diagnose_round({"answer": "anything"}, "") is None


# --- _TokenCounter ---------------------------------------------------------


def test_token_counter_accumulates_calls_and_tokens():
    sink: Dict[str, Dict[str, Any]] = {}
    wrapped = runner._TokenCounter(MockClient(tokens_per_call=25), sink, "student")
    wrapped.chat(messages=[{"role": "user", "content": "hi"}], temperature=0.0, max_tokens=10, timeout_s=5)
    wrapped.chat(messages=[{"role": "user", "content": "hi again"}], temperature=0.0, max_tokens=10, timeout_s=5)
    assert sink["student"]["calls"] == 2
    assert sink["student"]["tokens"] == 50
    assert sink["student"]["seconds"] >= 0.0


# --- run_experiment: full composition through registries, mocked clients --


def test_run_experiment_end_to_end_arm_a_mocked(tmp_path, monkeypatch, tiny_dataset):
    """Arm A, memory=none, mocked student/judge clients (build_client
    monkeypatched) — proves config->blocks composition + rounds/summary
    shape without any network call."""
    monkeypatch.setattr(runner, "build_client", lambda provider, **kw: MockClient())

    cfg = _cfg("A")
    run_dir = tmp_path / "run1"
    run_dir.mkdir()

    summary = runner.run_experiment(cfg, Path("experiments/trackA_p2_armA_diabetes.yml"), tiny_dataset, None, run_dir)

    assert summary["num_questions"] == 2
    assert summary["arm"] == "A"
    assert summary["memory_type"] == "none"
    assert 0.0 <= summary["pass_rate"] <= 1.0
    assert summary["passed_count"] <= summary["num_questions"]
    assert summary["metrics"]["reference_match"]["semantic_sim_mean"] is not None
    assert summary["student_calls"]["calls"] == 2  # arm A = 1 call/question, 2 questions
    assert summary["teacher_calls"]["calls"] == 0  # arm A never calls the teacher
    assert summary["judge_calls"]["calls"] == 2
    assert summary["git_commit"] is None or isinstance(summary["git_commit"], str)
    assert "config_used" in summary

    rounds_path = run_dir / "rounds.jsonl"
    summary_path = run_dir / "summary.jsonl"
    assert rounds_path.is_file()
    assert summary_path.is_file()

    import json

    round_lines = [json.loads(l) for l in rounds_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(round_lines) == 2  # 1 round each for arm A
    for row in round_lines:
        assert row["arm"] == "A"
        assert row["memory_type"] == "none"
        assert "reference_match" in row
        assert row["reference_match"] is not None  # dataset has a ground-truth answer

    summary_lines = [json.loads(l) for l in summary_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(summary_lines) == 1
    assert summary_lines[0]["run_id"] == run_dir.name


def test_run_experiment_arm_d_requires_ground_truth_flows_through(tmp_path, monkeypatch, tiny_dataset):
    """Arm D pulls ground_truth from the dataset record (via runner, not the
    student path) — this smoke-proves the wiring without asserting on model
    quality."""
    monkeypatch.setattr(runner, "build_client", lambda provider, **kw: MockClient())
    cfg = _cfg("D")
    run_dir = tmp_path / "run_d"
    run_dir.mkdir()
    summary = runner.run_experiment(cfg, Path("experiments/trackA_p2_armD_diabetes.yml"), tiny_dataset, 1, run_dir)
    assert summary["arm"] == "D"
    assert summary["num_questions"] == 1


def test_run_experiment_empty_dataset_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "build_client", lambda provider, **kw: MockClient())
    empty = tmp_path / "empty.jsonl"
    empty.write_text("", encoding="utf-8")
    with pytest.raises(RuntimeError, match="no records loaded"):
        runner.run_experiment(_cfg("A"), Path("x.yml"), empty, None, tmp_path / "run_empty")


# --- summary shape vs schema.md experiment-summary shape -------------------


SCHEMA_REQUIRED_KEYS = {
    "experiment_id",
    "num_questions",
    "passed_count",
    "pass_rate",
    "seed",
    "metrics",
    "avg_rounds",
    "timestamp",
    "config_used",
}


def test_summary_has_schema_required_fields(tmp_path, monkeypatch, tiny_dataset):
    monkeypatch.setattr(runner, "build_client", lambda provider, **kw: MockClient())
    run_dir = tmp_path / "run_shape"
    run_dir.mkdir()
    summary = runner.run_experiment(_cfg("A"), Path("x.yml"), tiny_dataset, None, run_dir)
    missing = SCHEMA_REQUIRED_KEYS - set(summary)
    assert not missing, f"summary missing schema.md required fields: {missing}"


# --- CLI arg handling -------------------------------------------------------


def test_main_requires_config_arg():
    with pytest.raises(SystemExit):
        runner.main([])


def test_main_wires_data_and_limit(tmp_path, monkeypatch, tiny_dataset):
    """--config/--data/--limit/--runs-dir all reach run_experiment correctly,
    with mocked clients so no network call happens."""
    monkeypatch.setattr(runner, "build_client", lambda provider, **kw: MockClient())

    exp_path = write_yaml(tmp_path / "trackA_p2_armA_test.yml", ARM_A_OVERRIDE)
    runs_dir = tmp_path / "runs_out"

    rc = runner.main(
        [
            "--config",
            str(exp_path),
            "--data",
            str(tiny_dataset),
            "--limit",
            "1",
            "--runs-dir",
            str(runs_dir),
        ]
    )
    assert rc == 0
    run_dirs = list(runs_dir.iterdir())
    assert len(run_dirs) == 1
    assert (run_dirs[0] / "summary.jsonl").is_file()
    assert (run_dirs[0] / "config_used.json").is_file()
    assert (run_dirs[0] / "rounds.jsonl").is_file()


def test_main_default_data_path_is_heldout():
    """CLI parses --data as optional; when omitted the runner falls back to
    the real Diabetes heldout file (never the train split) — asserted via the
    module-level constant so this test doesn't need to run a full experiment."""
    assert runner.DEFAULT_DATA_PATH.name == "Diabetes_and_Digestive_and_Kidney_Diseases_heldout.jsonl"


# --- the "local" provider strangler override --------------------------------


def test_local_provider_is_ollama_not_tinyllama():
    """build decision 2: importing src.tlw.providers (done at
    src.tlw.runner import time) re-registers "local" -> OllamaClient,
    overwriting src/providers/local_client.py's LocalTinyLlama registration
    for any process that imports the new core."""
    from src.providers.factory import build_client
    from src.tlw.providers import OllamaClient

    client = build_client("local", model="qwen2.5:7b-instruct")
    assert isinstance(client, OllamaClient)
    assert client.name() == "local:qwen2.5:7b-instruct"


def test_local_provider_reregistration_is_silent_no_raise():
    """Verifies src/providers/factory.py's register() has no duplicate-name
    guard (docstring claim in src/tlw/providers.py) — re-importing/re-running
    the registration must not raise."""
    from src.providers.factory import _REGISTRY, register
    from src.core.client import LLMClient

    before = _REGISTRY["local"]

    @register("local")
    class _Temp(LLMClient):
        def name(self) -> str:
            return "temp"

        def chat(self, messages, temperature=0.2, top_p=1.0, max_tokens=256, timeout_s=30):
            raise NotImplementedError

    assert _REGISTRY["local"] is _Temp
    # restore so later tests (and later test files, if run in the same
    # session) still get the Ollama client, not this throwaway class.
    _REGISTRY["local"] = before


# --- _FallbackClient (teacher resilience for the long full run) ---


class _ErringClient:
    """Primary stub whose .chat either returns an error-result or raises."""

    def __init__(self, mode="error_result"):
        self.mode = mode
        self.calls = 0

    def name(self):
        return "primary:groq-qwen3-32b"

    def chat(self, messages, temperature=0.2, max_tokens=256, timeout_s=30):
        self.calls += 1
        if self.mode == "raise":
            raise RuntimeError("groq down")
        return SimpleNamespace(text="", error="429 rate limit", usage=None)


def test_fallback_used_when_primary_returns_error_result():
    """max_retries=0 -> immediate fallback on the first error (no backoff)."""
    sink: Dict[str, Dict[str, Any]] = {}
    primary = _ErringClient("error_result")
    fallback = MockClient(responses=["local feedback"])
    fb = runner._FallbackClient(primary, fallback, sink, max_retries=0, sleep_fn=lambda s: None)

    result = fb.chat(messages=[{"role": "user", "content": "coach me"}], temperature=0.0)

    assert result.text == "local feedback"       # fallback served it
    assert result.error is None
    assert primary.calls == 1                     # primary was tried once (no retries)
    assert len(fallback.calls) == 1               # fallback then invoked
    assert sink["teacher_fallback"]["count"] == 1
    assert fb.name() == "primary:groq-qwen3-32b"  # identity stays the primary's


def test_fallback_used_when_primary_raises():
    sink: Dict[str, Dict[str, Any]] = {}
    fb = runner._FallbackClient(
        _ErringClient("raise"), MockClient(responses=["local"]), sink, max_retries=0, sleep_fn=lambda s: None
    )
    result = fb.chat(messages=[{"role": "user", "content": "x"}])
    assert result.text == "local"
    assert sink["teacher_fallback"]["count"] == 1


def test_primary_success_never_touches_fallback():
    sink: Dict[str, Dict[str, Any]] = {}
    primary = MockClient(responses=["primary feedback"])
    fallback = MockClient(responses=["should not be used"])
    fb = runner._FallbackClient(primary, fallback, sink, sleep_fn=lambda s: None)

    result = fb.chat(messages=[{"role": "user", "content": "x"}])

    assert result.text == "primary feedback"
    assert len(fallback.calls) == 0
    assert sink["teacher_fallback"]["count"] == 0


# --- _FallbackClient: retry/backoff + no-fallback (2026-07-15 build) --------


def test_fallback_retries_primary_before_falling_back():
    """max_retries=2 -> primary is tried 3 times total (1 + 2 retries) before
    the fallback is used; each failed attempt sleeps once."""
    sink: Dict[str, Dict[str, Any]] = {}
    primary = _ErringClient("error_result")
    fallback = MockClient(responses=["local feedback"])
    sleeps: List[float] = []
    fb = runner._FallbackClient(
        primary, fallback, sink, max_retries=2, backoff_base=0.01, sleep_fn=sleeps.append
    )

    result = fb.chat(messages=[{"role": "user", "content": "x"}])

    assert result.text == "local feedback"
    assert primary.calls == 3          # 1 initial + 2 retries
    assert len(sleeps) == 2            # slept before each retry, not after the last failure
    assert sink["teacher_fallback"]["count"] == 1
    assert sink["teacher_fallback"]["primary_errors"] == 3
    assert sink["teacher_fallback"]["retries"] == 2


def test_fallback_honors_retry_after_hint_in_error_text():
    sink: Dict[str, Dict[str, Any]] = {}

    class _RetryAfterClient:
        def __init__(self):
            self.calls = 0

        def name(self):
            return "primary:groq"

        def chat(self, **kwargs):
            self.calls += 1
            return SimpleNamespace(text="", error="429: rate limited, retry-after: 3.5", usage=None)

    sleeps: List[float] = []
    fb = runner._FallbackClient(
        _RetryAfterClient(), MockClient(responses=["ok"]), sink, max_retries=1, sleep_fn=sleeps.append
    )
    fb.chat(messages=[{"role": "user", "content": "x"}])
    assert sleeps == [3.5]  # parsed straight from the error text, not the exponential default


def test_no_fallback_configured_retries_then_returns_null_without_raising():
    """The 70B case (hub instruction: never fall back to local for a 70B) —
    pace/retry only; once exhausted, degrade to a null/error result and let
    the run continue rather than raising."""
    sink: Dict[str, Dict[str, Any]] = {}
    primary = _ErringClient("error_result")
    fb = runner._FallbackClient(primary, None, sink, max_retries=1, sleep_fn=lambda s: None)

    result = fb.chat(messages=[{"role": "user", "content": "x"}])

    assert result.text == ""
    assert result.error is not None
    assert primary.calls == 2  # 1 initial + 1 retry, no exception raised out
    assert sink["teacher_fallback"]["count"] == 0
    assert sink["teacher_fallback"]["exhausted_no_fallback"] == 1


def test_fallback_sink_key_isolates_teacher_and_judge_stats():
    """Two independently-wrapped slots (teacher, judge) must not share a
    stats bucket — each gets its own sink_key."""
    sink: Dict[str, Dict[str, Any]] = {}
    teacher_fb = runner._FallbackClient(
        _ErringClient("error_result"),
        MockClient(responses=["t"]),
        sink,
        sink_key="teacher_fallback",
        max_retries=0,
        sleep_fn=lambda s: None,
    )
    judge_fb = runner._FallbackClient(
        _ErringClient("error_result"),
        MockClient(responses=["j"]),
        sink,
        sink_key="judge_fallback",
        max_retries=0,
        sleep_fn=lambda s: None,
    )
    teacher_fb.chat(messages=[{"role": "user", "content": "x"}])
    assert sink["teacher_fallback"]["count"] == 1
    assert sink["judge_fallback"]["count"] == 0  # bucket exists (eager setdefault) but untouched
    judge_fb.chat(messages=[{"role": "user", "content": "x"}])
    assert sink["judge_fallback"]["count"] == 1
    assert sink["teacher_fallback"]["count"] == 1  # untouched by the judge call


# --- --teacher-fallback / --judge-fallback CLI wiring (2026-07-15 build) ---


def test_parse_provider_model_splits_on_first_colon_only():
    """Ollama model tags contain a colon themselves (`qwen2.5:7b-instruct`) —
    the split must not break them apart."""
    assert runner._parse_provider_model("local:qwen2.5:7b-instruct") == ("local", "qwen2.5:7b-instruct")
    assert runner._parse_provider_model("groq:llama-3.1-8b-instant") == ("groq", "llama-3.1-8b-instant")


def test_parse_provider_model_rejects_missing_colon():
    import argparse

    with pytest.raises(argparse.ArgumentTypeError):
        runner._parse_provider_model("bare-model-name-no-colon")


def test_main_wires_teacher_and_judge_fallback_flags(tmp_path, monkeypatch, tiny_dataset):
    """--teacher-fallback / --judge-fallback reach run_experiment as parsed
    (provider, model) tuples, and land in the summary as provenance."""
    captured: Dict[str, Any] = {}
    real_run_experiment = runner.run_experiment

    def spy(cfg, config_path, data_path, limit, run_dir, **kwargs):
        captured.update(kwargs)
        return real_run_experiment(cfg, config_path, data_path, limit, run_dir, **kwargs)

    monkeypatch.setattr(runner, "build_client", lambda provider, **kw: MockClient())
    monkeypatch.setattr(runner, "run_experiment", spy)

    exp_path = write_yaml(tmp_path / "trackA_full_armC_test.yml", ARM_C_OVERRIDE)
    runs_dir = tmp_path / "runs_out"

    rc = runner.main(
        [
            "--config", str(exp_path),
            "--data", str(tiny_dataset),
            "--limit", "1",
            "--runs-dir", str(runs_dir),
            "--teacher-fallback", "local:qwen2.5:7b-instruct",
            "--judge-fallback", "local:llama3.1:8b",
        ]
    )
    assert rc == 0
    assert captured["teacher_fallback"] == ("local", "qwen2.5:7b-instruct")
    assert captured["judge_fallback"] == ("local", "llama3.1:8b")

    run_dirs = list(runs_dir.iterdir())
    summary = json.loads((run_dirs[0] / "summary.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert summary["teacher_fallback_configured"] == "local:qwen2.5:7b-instruct"
    assert summary["judge_fallback_configured"] == "local:llama3.1:8b"


def test_main_legacy_teacher_fallback_model_flag_maps_to_local():
    """--teacher-fallback-model (original, local-only) still works as a
    deprecated alias for --teacher-fallback local:<model>."""
    parser_args = ["--config", "x.yml", "--teacher-fallback-model", "qwen2.5:7b-instruct"]
    import argparse as _argparse

    # Just exercise the arg-parsing branch in main() without a real run: call
    # main with a config path that will fail to load, and assert we get past
    # arg parsing (SystemExit only on argparse errors, not on config load).
    with pytest.raises(Exception) as exc_info:
        runner.main(parser_args)
    assert not isinstance(exc_info.value, SystemExit)  # argparse accepted the flag

"""Unit tests for Config Contract v1 validation rules V1-V8.

Each rule gets its own test (step 3), plus a broken-config test proving
all violations are reported together (fail-loud DoD).
"""

import copy

import pytest

from src.tlw.config import ConfigValidationError, validate


def valid_config():
    """A minimal config satisfying every contract rule (arm C headline shape)."""
    return {
        "student": {"provider": "local", "model": "qwen2.5:7b-instruct", "temperature": 0.3},
        "teacher": {"provider": "groq", "model": "qwen/qwen3-32b", "temperature": 0.0},
        "preset": {"student": "minimal", "teacher": "orca"},
        "memory": {"type": "none", "top_k": 3, "similarity_threshold": 0.75},
        "params": {"seed": 42, "arm": "C", "max_rounds": 3},
        "eval": {
            "judge": {"provider": "local", "model": "llama3.1:8b", "temperature": 0.0},
            "mode": "blind",
            "pass_threshold": 0.75,
            "metrics": {"weights": {"blind_score": 1.0}},
        },
    }


def errors_of(cfg):
    with pytest.raises(ConfigValidationError) as exc:
        validate(cfg)
    return exc.value.errors


def assert_single_rule(cfg, rule):
    errs = errors_of(cfg)
    assert len(errs) == 1, errs
    assert errs[0].startswith(f"{rule} —"), errs[0]
    return errs[0]


def test_valid_config_passes():
    validate(valid_config())  # must not raise


# --- V1: metric weights sum to 1.0 ± eps ---

def test_v1_weights_must_sum_to_one():
    cfg = valid_config()
    cfg["eval"]["metrics"]["weights"] = {"blind_score": 0.5, "semantic_sim": 0.4}
    msg = assert_single_rule(cfg, "V1")
    assert "0.9" in msg


def test_v1_accepts_multi_metric_sum():
    cfg = valid_config()
    cfg["eval"]["metrics"]["weights"] = {"blind_score": 0.7, "semantic_sim": 0.2, "rouge_l": 0.1}
    validate(cfg)


# --- V2: judge family ≠ student family (§0.2) ---

def test_v2_same_family_rejected():
    cfg = valid_config()
    cfg["eval"]["judge"]["model"] = "qwen/qwen3-32b"  # Qwen judge vs Qwen student
    msg = assert_single_rule(cfg, "V2")
    assert "§0.2" in msg


def test_v2_unknown_family_rejected():
    cfg = valid_config()
    cfg["student"]["model"] = "mistral-7b-instruct"
    msg = assert_single_rule(cfg, "V2")
    assert "cannot determine model family" in msg


# --- V3: unknown keys rejected ---

def test_v3_typo_key_rejected():
    cfg = valid_config()
    cfg["eval"]["pass_treshold"] = 0.7  # the exact typo the spec names
    msg = assert_single_rule(cfg, "V3")
    assert "eval.pass_treshold" in msg


def test_v3_unknown_slot_rejected():
    cfg = valid_config()
    cfg["telemetry"] = {"enabled": True}
    msg = assert_single_rule(cfg, "V3")
    assert "telemetry" in msg


def test_v3_unknown_metric_weight_rejected():
    cfg = valid_config()
    cfg["eval"]["metrics"]["weights"] = {"blind_score": 0.5, "blindscore": 0.5}
    msg = assert_single_rule(cfg, "V3")
    assert "weights.blindscore" in msg


# --- V4: seed mandatory (§0.3) ---

def test_v4_missing_seed_rejected():
    cfg = valid_config()
    del cfg["params"]["seed"]
    msg = assert_single_rule(cfg, "V4")
    assert "§0.3" in msg


def test_v4_non_integer_seed_rejected():
    cfg = valid_config()
    cfg["params"]["seed"] = "42"
    assert_single_rule(cfg, "V4")


# --- V5: thresholds live under slot F only ---

def test_v5_threshold_under_teacher_rejected():
    cfg = valid_config()
    cfg["teacher"]["pass_threshold"] = 0.8  # the simplified_config.yml:27 bug
    msg = assert_single_rule(cfg, "V5")
    assert "slot F" in msg


# --- V6: memory-store denylist (§0.2 seal #6) ---

@pytest.mark.parametrize(
    "path", ["logs/experiments/phase6/memory.jsonl", "seed/gt_memory_store.jsonl", "x/ground_truth.jsonl"]
)
def test_v6_denylisted_seed_store_rejected(path):
    cfg = valid_config()
    cfg["memory"]["seed_from"] = path
    msg = assert_single_rule(cfg, "V6")
    assert "seal #6" in msg


def test_v6_clean_relative_seed_store_allowed():
    cfg = valid_config()
    cfg["memory"]["seed_from"] = "logs/experiments/trackA_pilot/memory_episodes.jsonl"
    validate(cfg)


# --- V7: enums + numeric ranges ---

@pytest.mark.parametrize(
    "mutate",
    [
        lambda c: c["student"].update(provider="openai"),
        lambda c: c["memory"].update(type="redis"),
        lambda c: c["params"].update(arm="E"),
        lambda c: c["eval"].update(mode="sighted"),
        lambda c: c["memory"].update(top_k=0),
        lambda c: c["eval"].update(pass_threshold=1.5),
        lambda c: c["params"].update(max_rounds=-1),
        lambda c: c["student"].update(temperature=-0.1),
    ],
)
def test_v7_bad_enum_or_range_rejected(mutate):
    cfg = valid_config()
    mutate(cfg)
    assert_single_rule(cfg, "V7")


# --- V8: arm × memory cross-check (ADR-022 (e)) ---

@pytest.mark.parametrize("arm", ["A", "B"])
def test_v8_baseline_arm_with_faiss_rejected(arm):
    # 'faiss' (an ACCUMULATING store) is still forbidden on the baseline arms.
    cfg = valid_config()
    cfg["params"]["arm"] = arm
    cfg["memory"]["type"] = "faiss"
    msg = assert_single_rule(cfg, "V8")
    assert "faiss" in msg


@pytest.mark.parametrize("arm", ["A", "B"])
def test_v8_baseline_arm_with_rag_allowed(arm):
    # 'rag' is a READ-ONLY corpus (ADR-026), exempt from V8 — the RAG headline
    # arms are single-pass arm A + memory.type: rag.
    cfg = valid_config()
    cfg["params"]["arm"] = arm
    cfg["memory"]["type"] = "rag"
    cfg["memory"]["corpus_path"] = "indexes/medquad-diabetes-train"
    validate(cfg)  # must not raise


@pytest.mark.parametrize(
    "arm,mem", [("A", "none"), ("B", "none"), ("C", "faiss"), ("D", "faiss")]
)
def test_v8_legal_combinations_pass(arm, mem):
    cfg = valid_config()
    cfg["params"]["arm"] = arm
    cfg["memory"]["type"] = mem
    validate(cfg)


def test_rag_requires_corpus_path():
    cfg = valid_config()
    cfg["params"]["arm"] = "A"
    cfg["memory"]["type"] = "rag"  # no corpus_path -> fail loud
    msg = assert_single_rule(cfg, "RAG")
    assert "corpus_path" in msg


def test_rag_corpus_path_must_be_relative():
    cfg = valid_config()
    cfg["params"]["arm"] = "A"
    cfg["memory"]["type"] = "rag"
    cfg["memory"]["corpus_path"] = "C:/abs/rag_index"
    # PATH rule fires (absolute path); RAG corpus_path presence is satisfied.
    with pytest.raises(Exception) as ei:
        validate(cfg)
    assert "PATH" in str(ei.value) and "corpus_path" in str(ei.value)


# --- PATH: absolute paths banned (§0.3) ---

@pytest.mark.parametrize("path", ["C:/Users/somebody/Desktop/store.jsonl", "/tmp/store.jsonl"])
def test_absolute_seed_from_rejected(path):
    cfg = valid_config()
    cfg["memory"]["seed_from"] = path
    msg = assert_single_rule(cfg, "PATH")
    assert "project-relative" in msg


# --- REQUIRED + fail-loud aggregation (DoD) ---

def test_missing_required_keys_named():
    cfg = valid_config()
    del cfg["preset"]["teacher"]
    del cfg["eval"]["mode"]
    errs = errors_of(cfg)
    assert any("preset.teacher" in e and e.startswith("REQUIRED") for e in errs)
    assert any("eval.mode" in e and e.startswith("REQUIRED") for e in errs)


def test_broken_config_reports_all_rules_at_once():
    """One deliberately-broken config -> every violated rule named in one raise."""
    cfg = valid_config()
    cfg["eval"]["metrics"]["weights"] = {"blind_score": 0.5}          # V1
    cfg["eval"]["judge"]["model"] = "qwen2.5:7b-instruct"             # V2
    cfg["eval"]["pass_treshold"] = 0.7                                # V3
    del cfg["params"]["seed"]                                         # V4
    cfg["teacher"]["pass_threshold"] = 0.8                            # V5
    cfg["memory"]["seed_from"] = "logs/experiments/phase6/mem.jsonl"  # V6
    cfg["eval"]["mode"] = "sighted"                                   # V7
    cfg["params"]["arm"] = "A"
    cfg["memory"]["type"] = "faiss"                                   # V8
    errs = errors_of(cfg)
    for rule in ("V1", "V2", "V3", "V4", "V5", "V6", "V7", "V8"):
        assert any(e.startswith(f"{rule} —") for e in errs), f"{rule} missing in:\n" + "\n".join(errs)

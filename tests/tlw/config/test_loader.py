"""Tests for the layered loader (T2.1): base -> experiment -> env, deep-merge,
env-var mapping, path resolution, typed access, and base.yml itself."""

from pathlib import Path

import pytest
import yaml

from src.tlw.config import (
    DEFAULT_BASE_PATH,
    PROJECT_ROOT,
    ConfigError,
    ConfigValidationError,
    deep_merge,
    load_config,
)

ARM_C_OVERRIDE = {"params": {"arm": "C", "seed": 42}}


def write_yaml(path: Path, data) -> Path:
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


@pytest.fixture
def arm_c_file(tmp_path):
    return write_yaml(tmp_path / "trackA_p2_armC_test.yml", ARM_C_OVERRIDE)


def test_base_yml_plus_minimal_experiment_loads(arm_c_file):
    """base.yml carries every default; an experiment file only needs identity
    (arm + seed). Values assert the P1 gate answers (ADR-022)."""
    cfg = load_config(experiment_path=arm_c_file, env={})
    assert (cfg.student.provider, cfg.student.model) == ("local", "qwen2.5:7b-instruct")
    assert (cfg.teacher.provider, cfg.teacher.model) == ("groq", "qwen/qwen3-32b")
    assert (cfg.preset.student, cfg.preset.teacher) == ("minimal", "orca")
    assert cfg.memory.type == "none"  # headline = memory-off (ADR-022 (c))
    assert (cfg.params.arm, cfg.params.seed, cfg.params.max_rounds) == ("C", 42, 3)
    assert (cfg.eval.judge.provider, cfg.eval.judge.model) == ("local", "llama3.1:8b")
    assert cfg.eval.mode == "blind"
    assert cfg.eval.pass_threshold == 0.75
    assert cfg.eval.weights == {"blind_score": 1.0}


def test_base_yml_alone_fails_v4_and_arm():
    """base.yml deliberately carries no run identity: loading it without an
    experiment override must fail on seed (V4) and arm (REQUIRED)."""
    with pytest.raises(ConfigValidationError) as exc:
        load_config(env={})
    errs = exc.value.errors
    assert any(e.startswith("V4") for e in errs)
    assert any("params.arm" in e for e in errs)


def test_deep_merge_keeps_sibling_keys(tmp_path):
    """An experiment that sets only memory.top_k keeps base's memory.type."""
    exp = write_yaml(
        tmp_path / "exp.yml", deep_merge(ARM_C_OVERRIDE, {"memory": {"top_k": 5}})
    )
    cfg = load_config(experiment_path=exp, env={})
    assert cfg.memory.top_k == 5
    assert cfg.memory.type == "none"
    assert cfg.memory.similarity_threshold == 0.75


def test_env_overrides_win_last(arm_c_file):
    cfg = load_config(
        experiment_path=arm_c_file,
        env={
            "EXPERIMENT_PARAMS_SEED": "7",
            "EXPERIMENT_EVAL_PASS_THRESHOLD": "0.9",
            "EXPERIMENT_STUDENT_TEMPERATURE": "0.0",
        },
    )
    assert cfg.params.seed == 7  # env beats the experiment file's 42
    assert cfg.eval.pass_threshold == 0.9
    assert cfg.student.temperature == 0.0


def test_unknown_env_override_fails_loud(arm_c_file):
    with pytest.raises(ConfigError, match="EXPERIMENT_PARAMS_SEEDS"):
        load_config(experiment_path=arm_c_file, env={"EXPERIMENT_PARAMS_SEEDS": "7"})


def test_legacy_env_convention_ignored(arm_c_file):
    """EXPERIMENT_DIR/PHASE/NAME belong to the frozen legacy loop; the new
    loader must coexist with them during the strangler period."""
    cfg = load_config(
        experiment_path=arm_c_file,
        env={"EXPERIMENT_DIR": "logs/experiments", "EXPERIMENT_PHASE": "x", "EXPERIMENT_NAME": "y"},
    )
    assert cfg.params.seed == 42


def test_seed_from_resolved_project_relative(tmp_path):
    rel = "logs/experiments/trackA_pilot/memory_episodes.jsonl"
    exp = write_yaml(
        tmp_path / "exp.yml",
        deep_merge(ARM_C_OVERRIDE, {"memory": {"type": "faiss", "seed_from": rel}}),
    )
    cfg = load_config(experiment_path=exp, env={})
    resolved = Path(cfg.memory.seed_from)
    assert resolved.is_absolute()
    assert resolved == (PROJECT_ROOT / rel).resolve()


def test_missing_files_fail_loud(tmp_path):
    with pytest.raises(ConfigError, match="experiment config not found"):
        load_config(experiment_path=tmp_path / "nope.yml", env={})
    with pytest.raises(ConfigError, match="base config not found"):
        load_config(base_path=tmp_path / "no_base.yml", env={})


def test_non_mapping_experiment_rejected(tmp_path):
    bad = tmp_path / "bad.yml"
    bad.write_text("- just\n- a\n- list\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="YAML mapping"):
        load_config(experiment_path=bad, env={})


def test_merged_config_recorded_for_reproducibility(arm_c_file):
    """to_dict() returns the fully-merged config for summary.jsonl
    config_used{} (§0.3) and is a defensive copy."""
    cfg = load_config(experiment_path=arm_c_file, env={"EXPERIMENT_PARAMS_SEED": "7"})
    d = cfg.to_dict()
    assert d["params"]["seed"] == 7
    assert d["student"]["model"] == "qwen2.5:7b-instruct"
    d["params"]["seed"] = 999
    assert cfg.to_dict()["params"]["seed"] == 7


def test_default_base_path_is_repo_base_yml():
    assert DEFAULT_BASE_PATH == PROJECT_ROOT / "config" / "base.yml"
    assert DEFAULT_BASE_PATH.is_file()

"""Every shipped experiment config must still load and validate.

Why this exists: the ADR-034 restructure regrouped and renamed every file under
`experiments/`, and nothing checked that they still parse. The check was done by
hand once, which is exactly the kind of check that rots. This makes it permanent.

The subtlety it encodes: a *multi-seed* config deliberately omits `params.seed`
because the seed is the run's identity and is supplied per invocation via
`EXPERIMENT_PARAMS_SEED`, so one file drives all pre-registered seeds
(schema.md Layering rule 4). Validating such a file with no seed in the
environment therefore *correctly* fails V4 — so these tests validate configs the
way they are actually run, and assert the seedless case fails for that one
reason and no other.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from src.tlw.config.loader import load_config
from src.tlw.config.validation import ConfigValidationError

EXPERIMENTS = Path(__file__).resolve().parents[3] / "experiments"
CONFIGS = sorted(EXPERIMENTS.rglob("*.yml"))


def test_experiments_directory_is_not_empty():
    """A glob that silently matches nothing would make every test below vacuous."""
    assert CONFIGS, f"no experiment configs found under {EXPERIMENTS}"


@pytest.mark.parametrize("cfg_path", CONFIGS, ids=lambda p: str(p.relative_to(EXPERIMENTS)))
def test_config_validates_as_invoked(cfg_path, monkeypatch):
    """Loads exactly as `run.py` does: with a seed available in the environment."""
    monkeypatch.setenv("EXPERIMENT_PARAMS_SEED", "42")
    cfg = load_config(cfg_path)
    assert cfg.params.seed == 42
    assert cfg.params.arm in {"A", "B", "C", "D"}


@pytest.mark.parametrize("cfg_path", CONFIGS, ids=lambda p: str(p.relative_to(EXPERIMENTS)))
def test_seedless_config_fails_only_on_the_seed_rule(cfg_path, monkeypatch):
    """A config with no seed anywhere must fail V4 — and nothing else.

    This is the guard that matters: it proves the *only* thing standing between a
    stored config and a valid run is the seed, so a real validation error (a bad
    model name, a §0.2 judge-family clash, an unknown key) can never hide behind
    the expected V4 message.
    """
    monkeypatch.delenv("EXPERIMENT_PARAMS_SEED", raising=False)
    try:
        load_config(cfg_path)
    except ConfigValidationError as exc:
        errors = str(exc)
        assert "V4" in errors, f"{cfg_path.name}: expected the seed rule, got:\n{errors}"
        for rule in ("V1", "V2", "V3", "V5", "V6", "V7", "V8", "REQUIRED", "PATH"):
            assert rule not in errors, (
                f"{cfg_path.name}: a real validation problem is hiding behind the "
                f"expected V4 seed message:\n{errors}"
            )


def test_no_config_hardcodes_an_absolute_path():
    """ADR-034 BLOCKER-2: a config that pins a machine path cannot be reproduced
    from a clone (§0.3). Applies to the config bodies, not the header comments."""
    offenders = []
    for p in CONFIGS:
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.split("#", 1)[0]
            if ":\\" in stripped or "C:/Users" in stripped:
                offenders.append(f"{p.relative_to(EXPERIMENTS)}:{i}")
    assert not offenders, f"absolute paths in experiment configs: {offenders}"

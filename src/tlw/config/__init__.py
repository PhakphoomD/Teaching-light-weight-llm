# Config block — six-slot Config Contract v1 loader + validation.
# Spec: .claude/rules/schema.md "Experiment Config Contract v1" (ADR-016/022).

from .loader import DEFAULT_BASE_PATH, PROJECT_ROOT, deep_merge, load_config
from .schema import (
    EarlyStopping,
    EvalSlot,
    ExperimentConfig,
    MemorySlot,
    ModelSlot,
    ParamsSlot,
    PresetSlot,
    model_family,
)
from .validation import ConfigError, ConfigValidationError, validate

__all__ = [
    "DEFAULT_BASE_PATH",
    "PROJECT_ROOT",
    "ConfigError",
    "ConfigValidationError",
    "EarlyStopping",
    "EvalSlot",
    "ExperimentConfig",
    "MemorySlot",
    "ModelSlot",
    "ParamsSlot",
    "PresetSlot",
    "deep_merge",
    "load_config",
    "model_family",
    "validate",
]

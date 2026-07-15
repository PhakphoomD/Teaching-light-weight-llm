"""Config Contract v1 — slot schema, enums, model families, typed views.

Spec: .claude/rules/schema.md "Experiment Config Contract v1" (ADR-016; gate
answers hardcoded per ADR-022). This module is data-only: the allowed-key tree,
the enum domains, the §0.2 family map, and the frozen dataclasses the loader
returns. Validation logic lives in validation.py, loading in loader.py.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

# --- Enum domains (Config Contract slot table + V7) ---

PROVIDERS = frozenset({"local", "groq", "gemini"})
MEMORY_TYPES = frozenset({"none", "faiss", "rag"})
ARMS = frozenset({"A", "B", "C", "D"})
EVAL_MODES = frozenset({"blind", "gt_comparing"})

# Metric names the eval block knows (schema.md Experiment-summary shape).
# An unknown weight key is a typo and must fail (V3), not silently vanish.
KNOWN_METRICS = frozenset(
    {"blind_score", "comparison_score", "semantic_sim", "rouge_l", "exact_match"}
)

# --- §0.2 family map (V2) — families per .claude/rules/providers.md ---

FAMILIES: Dict[str, frozenset] = {
    "llama": frozenset({"llama3.1:8b", "llama-3.1-8b-instant", "llama-3.3-70b-versatile"}),
    "qwen": frozenset(
        {"qwen2.5:7b-instruct", "qwen2.5:3b", "qwen/qwen3-32b", "qwen/qwen3.6-27b"}
    ),
}


def model_family(model: str) -> Optional[str]:
    """Family of a model name: exact map first, then substring heuristic.

    Returns None when the family cannot be determined — V2 then fails loud,
    because §0.2 cannot be verified for an unknown model.
    """
    for family, models in FAMILIES.items():
        if model in models:
            return family
    lowered = model.lower()
    hits = [f for f in FAMILIES if f in lowered]
    return hits[0] if len(hits) == 1 else None


# --- Allowed-key tree (V3: any key outside this tree is a hard error) ---
# Leaf = None (scalar); dict = nested mapping.

_MODEL_SLOT_KEYS: Dict[str, Any] = {
    "provider": None,
    "model": None,
    "temperature": None,
    "max_tokens": None,
    "timeout": None,
}

ALLOWED_KEYS: Dict[str, Any] = {
    "student": dict(_MODEL_SLOT_KEYS),  # A
    "teacher": dict(_MODEL_SLOT_KEYS),  # B
    "preset": {"student": None, "teacher": None},  # C — preset NAMES, not prompt text
    "memory": {  # D — optional keys incl. Memory v2 tripwire thresholds (ADR-018)
        "type": None,
        "embedding": None,
        "top_k": None,
        "similarity_threshold": None,
        "min_success_rate": None,
        "max_episodes": None,
        "gt_substring_shingle": None,
        "gt_similarity_max": None,
        "seed_from": None,
    },
    "params": {  # E
        "seed": None,
        "arm": None,
        "max_rounds": None,
        "early_stopping": {
            "enabled": None,
            "patience": None,
            "min_improvement": None,
            "plateau_threshold": None,
            "start_from_round": None,
        },
    },
    "eval": {  # F — thresholds live HERE, never under teacher (V5)
        "judge": dict(_MODEL_SLOT_KEYS),
        "mode": None,
        "pass_threshold": None,
        "metrics": {"weights": {m: None for m in KNOWN_METRICS}},
    },
}

# Required keys per slot (dotted paths). params.seed has its own rule (V4).
REQUIRED_KEYS: Tuple[str, ...] = (
    "student.provider",
    "student.model",
    "teacher.provider",
    "teacher.model",
    "preset.student",
    "preset.teacher",
    "memory.type",
    "params.arm",
    "eval.judge.provider",
    "eval.judge.model",
    "eval.mode",
    "eval.metrics.weights",
)

# V6 — memory-store denylist (LEAKAGE_CENSUS seal #6): GT-seeded historical
# artifacts may never feed a measured run.
MEMORY_PATH_DENYLIST: Tuple[str, ...] = ("phase6", "gt_memory", "ground_truth")


# --- Typed views (defaults live in config/base.yml ONLY — dataclasses carry
#     no numeric defaults, so a value can never exist in two places) ---


@dataclass(frozen=True)
class ModelSlot:
    provider: str
    model: str
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    timeout: Optional[int] = None


@dataclass(frozen=True)
class PresetSlot:
    student: str
    teacher: str


@dataclass(frozen=True)
class MemorySlot:
    type: str
    embedding: Optional[str] = None
    top_k: Optional[int] = None
    similarity_threshold: Optional[float] = None
    min_success_rate: Optional[float] = None
    max_episodes: Optional[int] = None
    gt_substring_shingle: Optional[int] = None
    gt_similarity_max: Optional[float] = None
    seed_from: Optional[str] = None  # resolved project-relative by the loader


@dataclass(frozen=True)
class EarlyStopping:
    enabled: Optional[bool] = None
    patience: Optional[int] = None
    min_improvement: Optional[float] = None
    plateau_threshold: Optional[float] = None
    start_from_round: Optional[int] = None


@dataclass(frozen=True)
class ParamsSlot:
    seed: int
    arm: str
    max_rounds: Optional[int] = None
    early_stopping: Optional[EarlyStopping] = None


@dataclass(frozen=True)
class EvalSlot:
    judge: ModelSlot
    mode: str
    pass_threshold: Optional[float] = None
    weights: Dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class ExperimentConfig:
    """The six slots, plus the fully-merged raw dict for run recording (§0.3).

    `to_dict()` is what the runner writes into summary.jsonl `config_used{}`
    so every number is reproducible from its exact config.
    """

    student: ModelSlot
    teacher: ModelSlot
    preset: PresetSlot
    memory: MemorySlot
    params: ParamsSlot
    eval: EvalSlot
    _merged: Dict[str, Any] = field(default_factory=dict, repr=False)

    def to_dict(self) -> Dict[str, Any]:
        import copy

        return copy.deepcopy(self._merged)

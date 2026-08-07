"""Config Contract v1 loader — layered loading + env overrides + typed access.

Merge order (last wins, schema.md Layering rule 3):
    config/base.yml  ->  experiments/<file>.yml  ->  EXPERIMENT_* env overrides

The fully-merged dict is validated (validation.py, rules V1-V8) before any
typed object is built, and is kept on the returned ExperimentConfig so the
runner can record it verbatim into summary.jsonl `config_used{}` (§0.3/§0.4).
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

import yaml

from .schema import (
    ALLOWED_KEYS,
    EarlyStopping,
    EvalSlot,
    ExperimentConfig,
    MemorySlot,
    ModelSlot,
    ParamsSlot,
    PresetSlot,
)
from .validation import ConfigError, validate

# loader.py -> config -> tlw -> src -> <project root>
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_BASE_PATH = PROJECT_ROOT / "config" / "base.yml"

ENV_PREFIX = "EXPERIMENT_"
# Legacy logging convention consumed by the frozen loop
# (config/simplified_config.yml:105) — ignored here so both cores can coexist
# during the strangler period; retired with the legacy in T2.9.
LEGACY_ENV_KEYS = frozenset({"EXPERIMENT_DIR", "EXPERIMENT_PHASE", "EXPERIMENT_NAME"})


def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Recursive dict merge, override wins; non-dict values replace wholesale."""
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _load_yaml_mapping(path: Path, what: str) -> Dict[str, Any]:
    if not path.is_file():
        raise ConfigError(f"{what} not found: {path}")
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ConfigError(f"{what} must be a YAML mapping, got {type(data).__name__}: {path}")
    return data


def _resolve_env_key(remainder: str, tree: Any) -> Optional[List[str]]:
    """Map an env-var tail (lowercased, e.g. 'eval_pass_threshold') onto a
    dotted path in the allowed-key tree. Longest key match wins so keys that
    themselves contain underscores (pass_threshold, max_rounds) resolve."""
    if not isinstance(tree, dict):
        return None
    for key in sorted(tree, key=len, reverse=True):
        if remainder == key:
            return [key]
        if remainder.startswith(key + "_"):
            sub = _resolve_env_key(remainder[len(key) + 1 :], tree[key])
            if sub is not None:
                return [key] + sub
    return None


def _env_overrides(env: Mapping[str, str]) -> Dict[str, Any]:
    """EXPERIMENT_* variables -> nested override dict (schema.md Layering rule 4).
    Values are parsed as YAML scalars (EXPERIMENT_PARAMS_SEED=7 -> int 7).
    An EXPERIMENT_* name that maps to no contract key fails loud (V3 spirit)."""
    override: Dict[str, Any] = {}
    for name, raw in env.items():
        if not name.startswith(ENV_PREFIX) or name in LEGACY_ENV_KEYS:
            continue
        path = _resolve_env_key(name[len(ENV_PREFIX) :].lower(), ALLOWED_KEYS)
        if path is None:
            raise ConfigError(
                f"Environment override {name!r} does not map to any Config Contract "
                f"key (V3: typos must fail, not vanish)"
            )
        try:
            value = yaml.safe_load(raw)
        except yaml.YAMLError:
            value = raw
        node = override
        for part in path[:-1]:
            node = node.setdefault(part, {})
        node[path[-1]] = value
    return override


def _resolve_paths(cfg: Dict[str, Any]) -> None:
    """Resolve project-relative config paths against the repo root (in place).
    Validation has already rejected absolute paths (PATH rule)."""
    memory = cfg.get("memory")
    if isinstance(memory, dict) and memory.get("seed_from"):
        memory["seed_from"] = str((PROJECT_ROOT / str(memory["seed_from"])).resolve())
    if isinstance(memory, dict) and memory.get("corpus_path"):
        memory["corpus_path"] = str((PROJECT_ROOT / str(memory["corpus_path"])).resolve())


def _build_model_slot(d: Dict[str, Any]) -> ModelSlot:
    return ModelSlot(
        provider=d["provider"],
        model=d["model"],
        temperature=d.get("temperature"),
        max_tokens=d.get("max_tokens"),
        timeout=d.get("timeout"),
    )


def _build_typed(cfg: Dict[str, Any]) -> ExperimentConfig:
    params = cfg["params"]
    es = params.get("early_stopping")
    eval_cfg = cfg["eval"]
    return ExperimentConfig(
        student=_build_model_slot(cfg["student"]),
        teacher=_build_model_slot(cfg["teacher"]),
        preset=PresetSlot(student=cfg["preset"]["student"], teacher=cfg["preset"]["teacher"]),
        memory=MemorySlot(
            type=cfg["memory"]["type"],
            embedding=cfg["memory"].get("embedding"),
            top_k=cfg["memory"].get("top_k"),
            similarity_threshold=cfg["memory"].get("similarity_threshold"),
            min_success_rate=cfg["memory"].get("min_success_rate"),
            max_episodes=cfg["memory"].get("max_episodes"),
            gt_substring_shingle=cfg["memory"].get("gt_substring_shingle"),
            gt_similarity_max=cfg["memory"].get("gt_similarity_max"),
            seed_from=cfg["memory"].get("seed_from"),
            corpus_path=cfg["memory"].get("corpus_path"),
            max_passage_words=cfg["memory"].get("max_passage_words"),
            aspect_rerank=cfg["memory"].get("aspect_rerank"),
        ),
        params=ParamsSlot(
            seed=params["seed"],
            arm=params["arm"],
            max_rounds=params.get("max_rounds"),
            early_stopping=EarlyStopping(**es) if isinstance(es, dict) else None,
        ),
        eval=EvalSlot(
            judge=_build_model_slot(eval_cfg["judge"]),
            mode=eval_cfg["mode"],
            pass_threshold=eval_cfg.get("pass_threshold"),
            weights=dict(eval_cfg["metrics"]["weights"]),
        ),
        _merged=cfg,
    )


def load_config(
    experiment_path: Optional[os.PathLike] = None,
    base_path: Optional[os.PathLike] = None,
    env: Optional[Mapping[str, str]] = None,
) -> ExperimentConfig:
    """Load base.yml (+ optional experiment override, + EXPERIMENT_* env),
    validate the merged result fail-loud, and return the typed config."""
    base = _load_yaml_mapping(Path(base_path) if base_path else DEFAULT_BASE_PATH, "base config")
    merged = base
    if experiment_path is not None:
        merged = deep_merge(merged, _load_yaml_mapping(Path(experiment_path), "experiment config"))
    merged = deep_merge(merged, _env_overrides(os.environ if env is None else env))
    validate(merged)
    _resolve_paths(merged)
    return _build_typed(merged)

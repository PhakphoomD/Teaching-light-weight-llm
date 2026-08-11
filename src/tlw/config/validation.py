"""Config Contract v1 validation — rules V1–V8 + required keys + path policy.

Fail-loud (ADR-016): ALL violations are collected and raised together as one
ConfigValidationError, each message prefixed with its rule id, so a broken
config shows every problem in one pass.
"""

import numbers
from typing import Any, Dict, List, Optional

from .schema import (
    ALLOWED_KEYS,
    ARMS,
    EVAL_MODES,
    MEMORY_PATH_DENYLIST,
    MEMORY_TYPES,
    PROVIDERS,
    REQUIRED_KEYS,
    model_family,
)

WEIGHT_EPSILON = 1e-6


class ConfigError(Exception):
    """Base error for the tlw config block."""


class ConfigValidationError(ConfigError):
    def __init__(self, errors: List[str]):
        self.errors = list(errors)
        lines = "\n".join(f"  - {e}" for e in self.errors)
        super().__init__(f"Config validation failed ({len(self.errors)} error(s)):\n{lines}")


def _get(cfg: Dict[str, Any], dotted: str) -> Any:
    node: Any = cfg
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def _is_number(v: Any) -> bool:
    return isinstance(v, numbers.Real) and not isinstance(v, bool)


def _check_required(cfg: Dict[str, Any], errors: List[str]) -> None:
    for dotted in REQUIRED_KEYS:
        if _get(cfg, dotted) is None:
            errors.append(f"REQUIRED — missing key '{dotted}' (Config Contract slot table)")


def _check_v5_threshold_placement(cfg: Dict[str, Any], errors: List[str]) -> List[str]:
    """V5 — thresholds live under slot F (eval) only. Returns the offending
    dotted keys so V3 does not double-report them."""
    offending = []
    teacher = cfg.get("teacher")
    if isinstance(teacher, dict):
        for key in teacher:
            if "threshold" in str(key):
                offending.append(f"teacher.{key}")
                errors.append(
                    f"V5 — 'teacher.{key}' is misplaced: thresholds belong under "
                    f"'eval.' (slot F), never under 'teacher:' "
                    f"(retires the config/simplified_config.yml:27 bug)"
                )
    return offending


def _check_v3_unknown_keys(
    node: Any, allowed: Any, path: str, errors: List[str], skip: List[str]
) -> None:
    if not isinstance(node, dict):
        return
    for key, value in node.items():
        dotted = f"{path}.{key}" if path else str(key)
        if dotted in skip:
            continue
        if not isinstance(allowed, dict) or key not in allowed:
            errors.append(f"V3 — unknown key '{dotted}' (typos must fail, not vanish)")
            continue
        _check_v3_unknown_keys(value, allowed[key], dotted, errors, skip)


def _check_v7_enums_and_types(cfg: Dict[str, Any], errors: List[str]) -> None:
    def enum(dotted: str, domain, label: str) -> None:
        v = _get(cfg, dotted)
        if v is not None and v not in domain:
            errors.append(f"V7 — {dotted} = {v!r} not in {sorted(domain)} ({label})")

    enum("student.provider", PROVIDERS, "slot A provider")
    enum("teacher.provider", PROVIDERS, "slot B provider")
    enum("eval.judge.provider", PROVIDERS, "slot F judge provider")
    enum("memory.type", MEMORY_TYPES, "slot D memory type")
    enum("params.arm", ARMS, "slot E arm (ADR-002)")
    enum("eval.mode", EVAL_MODES, "slot F judge mode")

    def numeric(dotted: str, lo=None, hi=None, integer=False, strict_lo=False) -> None:
        v = _get(cfg, dotted)
        if v is None:
            return
        if not _is_number(v) or (integer and not isinstance(v, int)):
            errors.append(f"V7 — {dotted} = {v!r} must be a{'n integer' if integer else ' number'}")
            return
        if lo is not None and (v <= lo if strict_lo else v < lo):
            op = ">" if strict_lo else ">="
            errors.append(f"V7 — {dotted} = {v!r} must be {op} {lo}")
        if hi is not None and v > hi:
            errors.append(f"V7 — {dotted} = {v!r} must be <= {hi}")

    for slot in ("student", "teacher", "eval.judge"):
        numeric(f"{slot}.temperature", lo=0)
        numeric(f"{slot}.max_tokens", lo=0, integer=True, strict_lo=True)
        numeric(f"{slot}.timeout", lo=0, strict_lo=True)
    numeric("memory.top_k", lo=0, integer=True, strict_lo=True)
    numeric("memory.similarity_threshold", lo=0, hi=1)
    numeric("memory.min_success_rate", lo=0, hi=1)
    numeric("memory.max_episodes", lo=0, integer=True, strict_lo=True)
    numeric("memory.gt_substring_shingle", lo=0, integer=True, strict_lo=True)
    numeric("memory.gt_similarity_max", lo=0, hi=1)
    numeric("memory.max_passage_words", lo=0, integer=True, strict_lo=True)
    numeric("params.max_rounds", lo=0, integer=True, strict_lo=True)
    numeric("eval.pass_threshold", lo=0, hi=1)

    weights = _get(cfg, "eval.metrics.weights")
    if isinstance(weights, dict):
        for name, w in weights.items():
            if not _is_number(w) or w < 0:
                errors.append(
                    f"V7 — eval.metrics.weights.{name} = {w!r} must be a number >= 0"
                )


def _check_v1_weights_sum(cfg: Dict[str, Any], errors: List[str]) -> None:
    weights = _get(cfg, "eval.metrics.weights")
    if not isinstance(weights, dict) or not weights:
        return  # absence is a REQUIRED error, not V1
    values = [w for w in weights.values() if _is_number(w)]
    if len(values) != len(weights):
        return  # non-numeric weights already reported by V7
    total = sum(values)
    if abs(total - 1.0) > WEIGHT_EPSILON:
        errors.append(
            f"V1 — eval.metrics.weights sum to {total}, must be 1.0 ± {WEIGHT_EPSILON} "
            f"(silent normalization masks a wrong config)"
        )


def _check_v2_judge_family(cfg: Dict[str, Any], errors: List[str]) -> None:
    student = _get(cfg, "student.model")
    judge = _get(cfg, "eval.judge.model")
    if not student or not judge:
        return
    sf, jf = model_family(str(student)), model_family(str(judge))
    if sf is None:
        errors.append(
            f"V2 — cannot determine model family of student.model = {student!r} "
            f"(§0.2 unverifiable; add it to the family map in providers.md/schema.py)"
        )
    if jf is None:
        errors.append(
            f"V2 — cannot determine model family of eval.judge.model = {judge!r} "
            f"(§0.2 unverifiable; add it to the family map in providers.md/schema.py)"
        )
    if sf is not None and jf is not None and sf == jf:
        errors.append(
            f"V2 — judge family must differ from student family (§0.2): "
            f"student {student!r} and judge {judge!r} are both '{sf}'"
        )


def _check_v4_seed(cfg: Dict[str, Any], errors: List[str]) -> None:
    seed = _get(cfg, "params.seed")
    if seed is None:
        errors.append(
            "V4 — params.seed is mandatory (§0.3 reproducibility). Supply it either "
            "(a) in the experiment file, for a config that names one specific run, or "
            "(b) via EXPERIMENT_PARAMS_SEED at invocation, which is how a multi-seed "
            "protocol drives the SAME file across its pre-registered seeds "
            "(schema.md Layering rule 4). Never as a base.yml default — that would give "
            "every run the same seed silently."
        )
    elif not isinstance(seed, int) or isinstance(seed, bool):
        errors.append(f"V4 — params.seed = {seed!r} must be an integer")


def _check_v6_memory_denylist(cfg: Dict[str, Any], errors: List[str]) -> None:
    seed_from = _get(cfg, "memory.seed_from")
    if not seed_from:
        return
    lowered = str(seed_from).lower()
    hits = [p for p in MEMORY_PATH_DENYLIST if p in lowered]
    if hits:
        errors.append(
            f"V6 — memory.seed_from = {seed_from!r} matches denylist {hits} "
            f"(§0.2, LEAKAGE_AUDIT seal #6: GT-seeded artifacts are quarantined)"
        )


def _check_v8_arm_memory(cfg: Dict[str, Any], errors: List[str]) -> None:
    arm = _get(cfg, "params.arm")
    mem_type = _get(cfg, "memory.type")
    # V8 (ADR-022 (e)) forbids arms A/B from ACCUMULATING notes ('faiss') — a
    # measured baseline must not learn. 'rag' is exempt (ADR-026 / schema.md
    # slot-D rag): it is a read-only corpus, not a note-accumulating store, so
    # the RAG headline arms (single-pass arm A + memory.type: rag) are legal.
    if arm in ("A", "B") and mem_type is not None and mem_type not in ("none", "rag"):
        errors.append(
            f"V8 — arm {arm!r} requires memory.type in {{none, rag}}, got {mem_type!r} "
            f"(ADR-022 (e): a measured baseline must not accumulate notes; "
            f"'faiss' memory-on is a C′/D′ ablation for arms C/D only. 'rag' is a "
            f"read-only corpus and is allowed on A/B, ADR-026)"
        )


def _check_rag_corpus_path(cfg: Dict[str, Any], errors: List[str]) -> None:
    """memory.type: rag REQUIRES a corpus_path (rag-medquad-protocol §2 / schema.md slot-D
    rag) — a rag run with no index must fail loud, not retrieve nothing silently."""
    if _get(cfg, "memory.type") != "rag":
        return
    if not _get(cfg, "memory.corpus_path"):
        errors.append(
            "RAG — memory.type: rag requires memory.corpus_path (a prebuilt "
            "tools/rag/ index dir, T3.2); none was given (rag-medquad-protocol §2)"
        )


def _check_paths(cfg: Dict[str, Any], errors: List[str]) -> None:
    """Path policy (step 3): config paths must be project-relative —
    kills hardcoded absolute paths (§0.3)."""
    from pathlib import PureWindowsPath, PurePosixPath

    def _reject_absolute(dotted: str) -> None:
        val = _get(cfg, dotted)
        if val is None:
            return
        s = str(val)
        if PureWindowsPath(s).is_absolute() or PurePosixPath(s).is_absolute():
            errors.append(
                f"PATH — {dotted} = {s!r} is absolute; config paths must be "
                f"project-relative (§0.3; the loader resolves them against the repo root)"
            )

    _reject_absolute("memory.seed_from")
    _reject_absolute("memory.corpus_path")  # rag index dir


def validate(cfg: Dict[str, Any]) -> None:
    """Run every contract rule on the fully-merged config dict; raise
    ConfigValidationError listing ALL violations, or return None if clean."""
    errors: List[str] = []
    if not isinstance(cfg, dict):
        raise ConfigValidationError(["config root must be a mapping of the six slots"])
    _check_required(cfg, errors)
    v5_offenders = _check_v5_threshold_placement(cfg, errors)
    _check_v3_unknown_keys(cfg, ALLOWED_KEYS, "", errors, skip=v5_offenders)
    _check_v7_enums_and_types(cfg, errors)
    _check_v1_weights_sum(cfg, errors)
    _check_v2_judge_family(cfg, errors)
    _check_v4_seed(cfg, errors)
    _check_v6_memory_denylist(cfg, errors)
    _check_v8_arm_memory(cfg, errors)
    _check_rag_corpus_path(cfg, errors)
    _check_paths(cfg, errors)
    if errors:
        raise ConfigValidationError(errors)

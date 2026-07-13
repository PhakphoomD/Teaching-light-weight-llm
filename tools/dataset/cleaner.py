"""
Deterministic dataset cleaner for MedQuAD-style Q&A.

Stage 1 of the Dataset Readiness Assessor. Pure stdlib + PyYAML so it runs
anywhere in the `tlw` env without heavy deps. Non-destructive: every record
keeps `answer_raw` and records what changed in `cleaning_flags` (see
`.claude/rules/schema.md`).

Rules live in `cleaning_config.yaml` — tune there, not here.
"""

from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import yaml

_WS = re.compile(r"\s+")
_MULTI_QMARK = re.compile(r"\s*\?(?:\s*\?)+")


# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #
@dataclass
class Config:
    raw: Dict[str, Any]

    @classmethod
    def load(cls, path: str | Path) -> "Config":
        with open(path, "r", encoding="utf-8") as f:
            return cls(yaml.safe_load(f))

    def __getitem__(self, key: str) -> Any:
        return self.raw[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self.raw.get(key, default)


# --------------------------------------------------------------------------- #
# Loading (jsonl or csv)
# --------------------------------------------------------------------------- #
def load_records(path: str | Path) -> List[Dict[str, Any]]:
    """Load raw records from .jsonl or .csv. Returns dicts with question/answer/source."""
    path = Path(path)
    records: List[Dict[str, Any]] = []
    if path.suffix.lower() == ".jsonl":
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                records.append(
                    {
                        "question": str(obj.get("question", "")),
                        "answer": str(obj.get("answer", "")),
                        "source": str(obj.get("source") or obj.get("topic") or path.stem),
                    }
                )
    elif path.suffix.lower() in {".csv", ".tsv"}:
        delim = "\t" if path.suffix.lower() == ".tsv" else ","
        with open(path, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f, delimiter=delim)
            for row in reader:
                q = row.get("Question") or row.get("question") or ""
                a = row.get("Answer") or row.get("answer") or row.get("reference") or ""
                records.append(
                    {"question": str(q), "answer": str(a), "source": path.stem}
                )
    else:
        raise ValueError(f"Unsupported input type: {path.suffix} ({path})")
    return records


# --------------------------------------------------------------------------- #
# Cleaning primitives
# --------------------------------------------------------------------------- #
def _norm_ws(text: str) -> str:
    return _WS.sub(" ", text.replace("\r", " ").replace("\n", " ")).strip()


def fix_question(question: str, cfg: Config) -> Tuple[str, List[str]]:
    flags: List[str] = []
    q = _norm_ws(question)
    if cfg["question"].get("collapse_multi_qmark", True) and _MULTI_QMARK.search(q):
        q = _MULTI_QMARK.sub("?", q)
        flags.append("fixed_multi_qmark")
    return q.strip(), flags


def strip_boilerplate(answer: str, cfg: Config) -> Tuple[str, List[str]]:
    """Apply boilerplate strippers in order; return (clean, flags)."""
    flags: List[str] = []
    a = _norm_ws(answer)

    # Leading "Key Points -" scaffold (NCI PDQ)
    if cfg["toggles"].get("strip_key_points", True):
        new = re.sub(r"^\s*Key Points\s*-\s*", "", a, flags=re.IGNORECASE)
        if new != a:
            flags.append("stripped_key_points")
            a = new

    for rule in cfg.get("answer_boilerplate", []):
        pat = re.compile(rule["pattern"], re.IGNORECASE)
        if pat.search(a):
            a = pat.sub(" ", a)
            flags.append(f"stripped_{rule['name']}")

    a = _norm_ws(a)
    return a, flags


def relabel_domain(source: str, cfg: Config) -> str:
    return cfg.get("domain_relabel", {}).get(source, source)


# --------------------------------------------------------------------------- #
# Record cleaning
# --------------------------------------------------------------------------- #
@dataclass
class CleanStats:
    n_input: int = 0
    dropped: Counter = field(default_factory=Counter)
    dropped_exact_dup: int = 0
    template_marked: int = 0
    flag_counts: Counter = field(default_factory=Counter)


def _norm_answer_key(answer: str) -> str:
    return _WS.sub(" ", answer.lower()).strip()


def clean_records(records: List[Dict[str, Any]], cfg: Config) -> Tuple[List[Dict[str, Any]], CleanStats]:
    stats = CleanStats(n_input=len(records))
    f = cfg["filter"]
    max_words_soft = int(cfg["toggles"].get("max_words_soft", 250))

    domain_counters: Dict[str, int] = defaultdict(int)
    cleaned: List[Dict[str, Any]] = []

    for rec in records:
        q_clean, q_flags = fix_question(rec["question"], cfg)
        a_clean, a_flags = strip_boilerplate(rec["answer"], cfg)
        flags = q_flags + a_flags

        # validation / filtering
        if f.get("drop_empty", True) and (not q_clean or not a_clean):
            stats.dropped["empty"] += 1
            continue
        if len(q_clean) < int(f.get("min_question_chars", 10)):
            stats.dropped["short_question"] += 1
            continue
        word_len = len(a_clean.split())
        if word_len < int(f.get("min_answer_words", 20)):
            stats.dropped["short_answer"] += 1
            continue

        if word_len > max_words_soft:
            flags.append("long_answer")

        domain = relabel_domain(rec["source"], cfg)
        idx = domain_counters[domain]
        domain_counters[domain] += 1

        for fl in flags:
            stats.flag_counts[fl] += 1

        cleaned.append(
            {
                "id": f"{domain}-{idx:05d}",
                "domain": domain,
                "question": q_clean,
                "answer": a_clean,
                "answer_raw": _norm_ws(rec["answer"]),
                "cleaning_flags": flags,
                "word_len": word_len,
                "is_template": False,
                "split": None,
                "_ans_key": _norm_answer_key(a_clean),
            }
        )

    cleaned = _dedup_and_mark_templates(cleaned, cfg, stats)
    for r in cleaned:
        r.pop("_ans_key", None)
    return cleaned, stats


def _dedup_and_mark_templates(
    records: List[Dict[str, Any]], cfg: Config, stats: CleanStats
) -> List[Dict[str, Any]]:
    d = cfg["dedup"]
    group_sizes = Counter(r["_ans_key"] for r in records)
    min_group = int(d.get("mark_template_min_group", 5))

    kept: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for r in records:
        key = r["_ans_key"]
        if d.get("exact_answer", True) and key in seen:
            stats.dropped_exact_dup += 1
            continue
        seen.add(key)
        if group_sizes[key] >= min_group:
            r["is_template"] = True
            stats.template_marked += 1
        kept.append(r)
    return kept


# --------------------------------------------------------------------------- #
# Persistence
# --------------------------------------------------------------------------- #
def write_jsonl(records: Iterable[Dict[str, Any]], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def clean_file(input_path: str | Path, output_path: str | Path, cfg: Config) -> CleanStats:
    records = load_records(input_path)
    cleaned, stats = clean_records(records, cfg)
    write_jsonl(cleaned, output_path)
    return stats

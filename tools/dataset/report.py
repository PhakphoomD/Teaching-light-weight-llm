"""
Deterministic quality metrics (automated A1) for before/after cleaning.

Covers the model-free parts of the rubric (see `.claude/rules/rubric.md`):
noise rate, duplication, length, question-template share. The full 7-dimension
readiness score (D4 quality via LLM-judge, D6 diversity / D3 near-dup via
embeddings, D7 answerability) is Stage 2.
"""

from __future__ import annotations

import re
import statistics
from collections import Counter
from typing import Any, Dict, List

_QTMPL = re.compile(
    r"what is \(are\)|who is at risk|how to diagnose|what are the symptoms of|"
    r"what causes|what are the treatments for|is .* inherited|how many people",
    re.IGNORECASE,
)
_DOUBLE_Q = re.compile(r"\?\s*\?")


def _boiler_patterns(cfg) -> List[re.Pattern]:
    pats = [re.compile(r["pattern"], re.IGNORECASE) for r in cfg.get("answer_boilerplate", [])]
    pats.append(re.compile(r"Key Points\s*-", re.IGNORECASE))
    return pats


def noise_rate(answers: List[str], cfg) -> float:
    if not answers:
        return 0.0
    pats = _boiler_patterns(cfg)
    hit = sum(1 for a in answers if any(p.search(a) for p in pats))
    return round(hit / len(answers), 4)


def _word_stats(answers: List[str]) -> Dict[str, Any]:
    lens = [len(a.split()) for a in answers] or [0]
    return {
        "median_words": int(statistics.median(lens)),
        "mean_words": round(statistics.fmean(lens), 1),
        "max_words": max(lens),
        "pct_lt20w": round(100 * sum(1 for x in lens if x < 20) / len(lens), 1),
        "pct_gt250w": round(100 * sum(1 for x in lens if x > 250) / len(lens), 1),
    }


def measure_raw(records: List[Dict[str, Any]], cfg) -> Dict[str, Any]:
    answers = [r["answer"] for r in records]
    questions = [r["question"] for r in records]
    return {
        "n": len(records),
        "noise_rate": noise_rate(answers, cfg),
        "double_qmark_questions": sum(1 for q in questions if _DOUBLE_Q.search(q)),
        "templated_question_pct": round(
            100 * sum(1 for q in questions if _QTMPL.search(q)) / max(len(questions), 1), 1
        ),
        "dup_answers": len(answers) - len(set(a.strip().lower() for a in answers)),
        **_word_stats(answers),
    }


def measure_clean(cleaned: List[Dict[str, Any]], cfg) -> Dict[str, Any]:
    answers = [r["answer"] for r in cleaned]
    return {
        "n": len(cleaned),
        "noise_rate": noise_rate(answers, cfg),
        "dup_answers": len(answers) - len(set(a.strip().lower() for a in answers)),
        "template_records": sum(1 for r in cleaned if r.get("is_template")),
        "domains": dict(Counter(r["domain"] for r in cleaned)),
        **_word_stats(answers),
    }

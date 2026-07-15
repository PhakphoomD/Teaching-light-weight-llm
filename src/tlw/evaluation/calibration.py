"""BlindJudge calibration probe (T2.3 / EVAL_SPEC.md §3.3).

Gates the judge BEFORE the real Track-A run. Built and run on the TRAIN
split (506 recs), NEVER the 125-question held-out set (§0.2). Extends the
label-free method of scripts/compare_judges.py (GOOD/WRONG/TRUNCATED) with
the spec's fourth, harder class:

  GOOD             the real cleaned train-split answer            -> PASS (3-4)
  WRONG            a fluent answer from a DIFFERENT question       -> FAIL (0-1)
  TRUNCATED        first ~12 words of the real answer              -> FAIL/borderline (0-2)
  PLAUSIBLE_WRONG  real answer with one fact heuristically negated -> FAIL (0-2), hardest class

Judge client: this script talks to the local Ollama daemon directly
(mirrors tools/dataset/judge.py's OllamaJudge, already proven working in
scripts/compare_judges.py) and injects it into BlindJudge via the `client=`
constructor param. See NEEDS-HUB-DECISION in the T2.3 report for why this
bypasses `build_client("local", ...)`: the registered "local" provider
(src/providers/local_client.py::LocalTinyLlama) is a HuggingFace-transformers
loader, not an Ollama client — "local" as used by config/base.yml (Ollama
models qwen2.5:7b-instruct / llama3.1:8b, per providers.md) has no matching
ProviderRegistry entry yet. That gap is out of T2.3's scope (owned by
T2.1/ops-engineer, the ProviderRegistry seam) but blocks a config-driven
judge from running end-to-end today.

Run (train split only, tlw env):
  & "C:\\Users\\ham25\\.conda\\envs\\tlw\\python.exe" -m src.tlw.evaluation.calibration --n 40
"""

from __future__ import annotations

import argparse
import json
import random
import re
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from statistics import fmean
from typing import Any, Dict, List, Optional

from .judge import BlindJudge

PROJECT_ROOT = Path(__file__).resolve().parents[3]
TRAIN_PATH = PROJECT_ROOT / "data" / "clean" / "Diabetes_and_Digestive_and_Kidney_Diseases_train.jsonl"
OUTPUT_DIR = PROJECT_ROOT / "runs" / "calibration"

# EVAL_SPEC §3.3 acceptance gates.
GATE_GOOD_PASS_RATE_MIN = 0.80
GATE_WRONG_PASS_RATE_MAX = 0.15
GATE_PLAUSIBLE_WRONG_PASS_RATE_MAX = 0.30
GATE_DISCRIMINATION_MIN = 0.6  # mean(GOOD) - mean(WRONG), normalized 0-1
GATE_KAPPA_MIN = 0.6
GATE_NULL_RATE_MAX = 0.02


@dataclass
class OllamaChatResult:
    text: str
    error: Optional[str] = None


class _OllamaAdapter:
    """Minimal LLMClient-shaped adapter over the Ollama HTTP API — used ONLY
    to drive BlindJudge for this probe (see module docstring). NOT registered
    into ProviderRegistry; not used by production judge construction."""

    def __init__(self, model: str = "llama3.1:8b", host: str = "http://localhost:11434"):
        self.model = model
        self.host = host.rstrip("/")

    def chat(self, messages, temperature: float, max_tokens: int, timeout_s: int) -> OllamaChatResult:
        payload = {
            "model": self.model,
            "messages": list(messages),
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        req = urllib.request.Request(
            f"{self.host}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout_s) as r:
                resp = json.loads(r.read())
            return OllamaChatResult(text=resp.get("message", {}).get("content", "") or "")
        except Exception as e:  # noqa: BLE001 - probe must not crash on one bad call
            return OllamaChatResult(text="", error=str(e))


class _GroqAdapter:
    """Same shape, for the Groq-70B calibration cross-check (§3.3 kappa gate),
    and (added for this probe) as the judge-under-test itself.

    Paced: llama-3.3-70b-versatile is capped at 12K TPM (providers.md), which
    a tight ~1s/call loop blows through in well under a minute (measured live:
    an unpaced n=20x4-class run 429'd on 47/80 calls -> 60% null rate, failing
    the null_rate gate). `min_interval_s` enforces a floor between call starts
    so sustained throughput stays under the TPM cap: at ~727 measured tokens/
    call (RUBRIC_PROMPT + a ~150-word medical answer), 4.0s/call ~= 9.1K tok/
    min, under 12K with margin. Independent of the judge under test when used
    only for the kappa cross-check (different provider entirely in that case)."""

    def __init__(self, model: str = "llama-3.3-70b-versatile", min_interval_s: float = 4.0):
        import os

        from dotenv import load_dotenv
        from groq import Groq

        load_dotenv()
        key = os.environ.get("GROQ_API_KEY")
        if not key:
            raise RuntimeError("GROQ_API_KEY not set")
        self._client = Groq(api_key=key)
        self.model = model
        self.min_interval_s = min_interval_s
        self._last_call_ts: Optional[float] = None

    def chat(self, messages, temperature: float, max_tokens: int, timeout_s: int) -> OllamaChatResult:
        if self._last_call_ts is not None:
            elapsed = time.time() - self._last_call_ts
            remaining = self.min_interval_s - elapsed
            if remaining > 0:
                time.sleep(remaining)
        self._last_call_ts = time.time()
        try:
            r = self._client.chat.completions.create(
                model=self.model,
                messages=list(messages),
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout_s,
            )
            choice = r.choices[0] if getattr(r, "choices", None) else None
            text = (choice.message.content if choice else "") or ""
            return OllamaChatResult(text=text)
        except Exception as e:  # noqa: BLE001
            return OllamaChatResult(text="", error=str(e))


# --- Probe construction (train split only, §0.2) ---

_FACT_NEGATION_MARKERS = [
    (r"\bis not\b", "is"),
    (r"\bare not\b", "are"),
    (r"\bcannot\b", "can"),
    (r"\bcan not\b", "can"),
    (r"\bdoes not\b", "does"),
    (r"\bdo not\b", "do"),
    (r"\bshould not\b", "should"),
    (r"\bwill not\b", "will"),
    (r"\bis\b", "is not"),
    (r"\bare\b", "are not"),
    (r"\bcan\b", "cannot"),
    (r"\bdoes\b", "does not"),
    (r"\bdo\b", "do not"),
    (r"\bshould\b", "should not"),
    (r"\bwill\b", "will not"),
]

_NUMBER_RE = re.compile(r"\b\d+(\.\d+)?\b")


def make_plausible_wrong(answer: str) -> str:
    """Heuristic clinically-material negation/alteration (EVAL_SPEC §3.3).

    Honesty note (§0.1): this is a deterministic RULE-BASED heuristic, not a
    clinically-validated adversarial generator. It flips the first polarity
    marker found (is/are/can/does/should/will <-> negated), or failing that,
    perturbs the first number by +/-30% (min delta 1). Not perfect, but
    label-free and reproducible — same posture as GOOD/WRONG/TRUNCATED.
    """
    for pattern, replacement in _FACT_NEGATION_MARKERS:
        m = re.search(pattern, answer, flags=re.IGNORECASE)
        if m:
            return answer[: m.start()] + replacement + answer[m.end():]

    m = _NUMBER_RE.search(answer)
    if m:
        try:
            val = float(m.group(0))
            delta = max(1.0, abs(val) * 0.3)
            new_val = val + delta
            new_str = str(int(new_val)) if val.is_integer() else f"{new_val:.1f}"
            return answer[: m.start()] + new_str + answer[m.end():]
        except ValueError:
            pass

    # Last resort: no polarity marker or number found — prefix a false claim.
    return "Contrary to standard guidance, " + answer[0].lower() + answer[1:] if answer else answer


def load_probe_candidates(n: int, seed: int) -> List[Dict[str, str]]:
    if not TRAIN_PATH.is_file():
        raise FileNotFoundError(f"train split not found: {TRAIN_PATH}")
    recs = [json.loads(l) for l in TRAIN_PATH.read_text(encoding="utf-8").splitlines() if l.strip()]
    rng = random.Random(seed)
    picked = rng.sample(recs, min(n, len(recs)))
    cands = []
    for i, r in enumerate(picked):
        other = picked[(i + 1) % len(picked)]
        words = r["answer"].split()
        cands.append(
            {
                "id": r["id"],
                "question": r["question"],
                "good": r["answer"],
                "wrong": other["answer"],
                "truncated": " ".join(words[:12]),
                "plausible_wrong": make_plausible_wrong(r["answer"]),
            }
        )
    return cands


# --- Probe execution ---

CLASSES = ("good", "wrong", "truncated", "plausible_wrong")


def run_probe(judge: BlindJudge, cands: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    rows = []
    for c in cands:
        row = {"id": c["id"], "question": c["question"]}
        for cls in CLASSES:
            verdict = judge.score(c["question"], c[cls], mode="blind")
            row[cls] = verdict["score"]
        rows.append(row)
    return rows


def _pass_rate(rows: List[Dict[str, Any]], cls: str, pass_threshold_score: int = 3) -> Dict[str, float]:
    scores = [r[cls] for r in rows]
    scored = [s for s in scores if s is not None]
    null_rate = 1.0 - (len(scored) / len(scores)) if scores else 1.0
    pass_rate = (sum(1 for s in scored if s >= pass_threshold_score) / len(scored)) if scored else float("nan")
    mean_norm = (fmean(scored) / 4.0) if scored else float("nan")
    return {"pass_rate": pass_rate, "null_rate": null_rate, "mean_normalized": mean_norm, "n": len(scores)}


def summarize(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    per_class = {cls: _pass_rate(rows, cls) for cls in CLASSES}
    discrimination = per_class["good"]["mean_normalized"] - per_class["wrong"]["mean_normalized"]
    gates = {
        "good_pass_rate_ge_0.80": per_class["good"]["pass_rate"] >= GATE_GOOD_PASS_RATE_MIN,
        "wrong_pass_rate_le_0.15": per_class["wrong"]["pass_rate"] <= GATE_WRONG_PASS_RATE_MAX,
        "plausible_wrong_pass_rate_le_0.30": per_class["plausible_wrong"]["pass_rate"]
        <= GATE_PLAUSIBLE_WRONG_PASS_RATE_MAX,
        "discrimination_ge_0.6": discrimination >= GATE_DISCRIMINATION_MIN,
        "null_rate_lt_0.02": all(per_class[c]["null_rate"] < GATE_NULL_RATE_MAX for c in CLASSES),
    }
    return {
        "per_class": per_class,
        "discrimination_good_minus_wrong": discrimination,
        "gates": gates,
        "all_gates_pass": all(gates.values()),
    }


def cohens_kappa_pass_fail(rows_a: List[Dict[str, Any]], rows_b: List[Dict[str, Any]], pass_threshold_score: int = 3) -> Optional[float]:
    """Cohen's kappa on the PASS/FAIL binary verdict between two judges over
    the same candidates (EVAL_SPEC §3.3 inter-judge agreement gate)."""
    pairs = []
    by_id_b = {(r["id"], cls): r[cls] for r in rows_b for cls in CLASSES}
    for r in rows_a:
        for cls in CLASSES:
            a = r[cls]
            b = by_id_b.get((r["id"], cls))
            if a is not None and b is not None:
                pairs.append((a >= pass_threshold_score, b >= pass_threshold_score))
    n = len(pairs)
    if n == 0:
        return None
    po = sum(1 for a, b in pairs if a == b) / n
    p_a_pass = sum(1 for a, _ in pairs if a) / n
    p_b_pass = sum(1 for _, b in pairs if b) / n
    pe = p_a_pass * p_b_pass + (1 - p_a_pass) * (1 - p_b_pass)
    if pe == 1.0:
        return 1.0 if po == 1.0 else 0.0
    return (po - pe) / (1 - pe)


_GROQ_MODEL_NAMES = {
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "qwen/qwen3-32b",
    "qwen/qwen3.6-27b",
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--model", default="llama3.1:8b")
    ap.add_argument(
        "--judge-provider",
        choices=["local", "groq"],
        default=None,
        help="force the judge-under-test provider; default = auto-detect from --model",
    )
    ap.add_argument("--skip-groq", action="store_true", help="skip the Groq-70B kappa cross-check")
    args = ap.parse_args()

    cands = load_probe_candidates(args.n, args.seed)
    print(f"Probe: {len(cands)} train-split questions x 4 classes (GOOD/WRONG/TRUNCATED/PLAUSIBLE_WRONG)")

    judge_provider = args.judge_provider or ("groq" if args.model in _GROQ_MODEL_NAMES else "local")
    if judge_provider == "groq":
        local_judge_client = _GroqAdapter(model=args.model)
        local_judge_label = f"groq/{args.model}"
    else:
        local_judge_client = _OllamaAdapter(model=args.model)
        local_judge_label = f"ollama/{args.model}"

    local_judge = BlindJudge(client=local_judge_client, pass_threshold=0.75)
    t0 = time.time()
    local_rows = run_probe(local_judge, cands)
    local_secs = time.time() - t0
    local_summary = summarize(local_rows)

    print(f"\n=== local judge: {local_judge_label} ({local_secs:.1f}s, {local_secs / (len(cands) * 4):.2f}s/call) ===")
    for cls in CLASSES:
        s = local_summary["per_class"][cls]
        print(
            f"  {cls:16s} pass_rate={s['pass_rate']:.2f}  mean_norm={s['mean_normalized']:.2f}  "
            f"null_rate={s['null_rate']:.2f}  n={s['n']}"
        )
    print(f"  discrimination (GOOD-WRONG, normalized): {local_summary['discrimination_good_minus_wrong']:+.2f}")
    print("  gates:")
    for name, ok in local_summary["gates"].items():
        print(f"    [{'PASS' if ok else 'FAIL'}] {name}")
    print(f"  ALL GATES PASS: {local_summary['all_gates_pass']}")

    result: Dict[str, Any] = {
        "n": len(cands),
        "seed": args.seed,
        "local_judge_model": local_judge_label,
        "local_summary": local_summary,
        "local_rows": local_rows,
        "kappa": None,
        "kappa_gate_pass": None,
        "kappa_not_applicable_reason": None,
        "groq_error": None,
    }

    cross_check_model = "llama-3.3-70b-versatile"
    self_comparison = judge_provider == "groq" and args.model == cross_check_model
    if self_comparison:
        # The judge-under-test IS the Groq-70B cross-check model: comparing it
        # to itself would yield kappa->1 by construction, not a real agreement
        # signal. Report N/A rather than fabricate a pass (task instructions).
        result["kappa_not_applicable_reason"] = (
            "judge-under-test is groq/llama-3.3-70b-versatile, identical to the "
            "kappa cross-check model — self-comparison is meaningless, skipped"
        )
        print(f"\n=== Groq-70B cross-check: N/A ({result['kappa_not_applicable_reason']}) ===")
    elif not args.skip_groq:
        try:
            groq_judge = BlindJudge(client=_GroqAdapter(model=cross_check_model), pass_threshold=0.75)
            t0 = time.time()
            groq_rows = run_probe(groq_judge, cands)
            groq_secs = time.time() - t0
            kappa = cohens_kappa_pass_fail(local_rows, groq_rows)
            result["groq_rows"] = groq_rows
            result["kappa"] = kappa
            result["kappa_gate_pass"] = (kappa is not None) and (kappa >= GATE_KAPPA_MIN)
            print(f"\n=== Groq-70B cross-check ({groq_secs:.1f}s) ===")
            print(f"  Cohen's kappa (local vs Groq-70B, PASS/FAIL): {kappa}")
            print(f"  [{'PASS' if result['kappa_gate_pass'] else 'FAIL'}] kappa_ge_0.6")
        except Exception as e:  # noqa: BLE001
            result["groq_error"] = str(e)
            print(f"\n=== Groq-70B cross-check: NOT VERIFIED ({e}) ===")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / f"probe_seed{args.seed}_n{args.n}_{int(time.time())}.json"
    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"\nWrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""
Simple Loop POC (single file)

Goals
- Dual-Score evaluation to reduce bias: deterministic metrics + teacher LLM score
- Memory-as-prompt via FAISS: cluster similar questions, store one evolving teaching
- Recommendation score: pick best prior teaching among similar questions
- Fact vs Principle: generate direct or principle-style teaching based on ground truth
- Keep minimal and reuse repo components; avoid heavy imports at module import time

Usage (pseudo):
    from src.simple_loop_poc import SimpleLoopPOC

    poc = SimpleLoopPOC(
        memory_dir="logs/memory",
        embedding_model="all-MiniLM-L6-v2",
    )

    # Provide callables for model access (you can wire your repo models)
    def student_client(prompt: str, max_tokens: int = 64) -> str:
        ...

    def llm_client(prompt: str, max_tokens: int = 128) -> str:
        ...

    result = poc.run(
        question="Separate words: helloworld",
        ground_truth="hello world",
        student_client=student_client,
        llm_client=llm_client,
        max_rounds=3,
    )
    print(result)

Notes
- English-only in operation; Thai examples were illustrative in design notes.
- This POC avoids importing heavy FAISS/embeddings until first use (lazy).
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

# Reuse deterministic metrics (lightweight imports)
from src.eval import metrics as det_metrics
from src.core.logger import get_logger

# Reuse the student prompt builder (we will pass our own 'hints' text)
from src.prompts.student import build_student_prompt


# -----------------------------
# Config defaults (tunable)
# -----------------------------

DEFAULTS = {
    "d_weights": {"exact": 0.4, "f1": 0.3, "bleu": 0.3},
    "agg": {"d_weight": 0.6, "t_weight": 0.4, "pass_threshold": 0.8, "disagreement_threshold": 0.3},
    "retrieval": {
        "student_k": 3,
        "student_threshold": 0.80,
        "refine_lower": 0.85,
        "reuse_threshold": 0.95,
        "teacher_k": 5,
    },
    "recommendation": {"smoothing_num": 1.0, "smoothing_den": 2.0},
    "prompt": {"student_max_tokens": 128, "teacher_max_tokens": 128},
}

logger = get_logger("simple_loop_poc")


# -----------------------------
# Data model
# -----------------------------

@dataclass
class MemoryRecord:
    id: str
    question_seed: str
    teaching_prompt: str
    teaching_type: str  # 'direct' | 'principle'
    used_count: int = 0
    success_count: int = 0
    recommendation_score: float = 0.0
    attempts: int = 0
    last_score: float = 0.0
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())


def _now_iso() -> str:
    return datetime.now().isoformat()


def _reco_score(success: int, used: int, smooth_num: float, smooth_den: float) -> float:
    return (success + smooth_num) / (used + smooth_den)


def _token_count(text: str) -> int:
    return len(text.strip().split()) if text else 0


# -----------------------------
# Lightweight teacher scoring and teaching prompts
# -----------------------------

def _teacher_score_prompt(question: str, student_answer: str, ground_truth: str) -> str:
    return (
        "You are a strict grader. Given the question, student answer, and ground truth, "
        "output ONLY a number between 0.0 and 1.0 for semantic correctness. No text, just the number.\n\n"
        f"Question: {question}\n"
        f"Student: {student_answer}\n"
        f"Ground truth: {ground_truth}\n\n"
        "Score:"
    )


def _principle_prompt(question: str, student_answer: str, ground_truth: str) -> str:
    return (
        "Create a short, general principle (<= 20 words) to solve questions like this. "
        "Do not reveal a specific example. Return only one line:\n"
        "Principle: ...\n\n"
        f"Question: {question}\n"
        f"Student answer: {student_answer}\n"
        f"Ground truth: {ground_truth}\n"
    )


def _refine_principle_prompt(prev_teaching: str, question: str, student_answer: str, ground_truth: str) -> str:
    return (
        f"Previous teaching: {prev_teaching}\n"
        f"Question: {question}\n"
        f"Student's latest answer: {student_answer}\n"
        f"Ground truth: {ground_truth}\n\n"
        "Think briefly: why did the previous teaching fail, and how to make it more general and actionable.\n"
        "Return only the improved teaching (<= 20 words), start with 'Principle: '."
    )


# -----------------------------
# Memory manager (reusing existing VectorIndex + MemoryStore lazily)
# -----------------------------

class MemoryManager:
    def __init__(
        self,
        memory_dir: str = "logs/memory",
        embedding_model: str = "all-MiniLM-L6-v2",
    ):
        # Lazy imports to avoid triggering heavy loads at module import time
        from src.refinement.memory.plugins.store import MemoryStore  # type: ignore
        from src.refinement.memory.plugins.vector_index import VectorIndex  # type: ignore

        self.store = MemoryStore(file_path=f"{memory_dir}/store.jsonl")
        self.index = VectorIndex(embedding_model=embedding_model, index_path=f"{memory_dir}/faiss.index")
        self.embedding_model = embedding_model

        # Build in-memory latest record map (id -> MemoryRecord)
        self.records: Dict[str, MemoryRecord] = {}
        for rec in self.store.load_records():
            try:
                # Accept only our schema records (have 'question_seed' and 'teaching_prompt')
                if "question_seed" in rec and "teaching_prompt" in rec:
                    self.records[rec["id"]] = MemoryRecord(
                        id=rec["id"],
                        question_seed=rec["question_seed"],
                        teaching_prompt=rec["teaching_prompt"],
                        teaching_type=rec.get("teaching_type", "principle"),
                        used_count=int(rec.get("used_count", 0)),
                        success_count=int(rec.get("success_count", 0)),
                        recommendation_score=float(rec.get("recommendation_score", 0.0)),
                        attempts=int(rec.get("attempts", 0)),
                        last_score=float(rec.get("last_score", 0.0)),
                        updated_at=rec.get("updated_at", _now_iso()),
                    )
            except Exception:
                # Skip malformed lines from legacy logs
                continue

    def _save_record(self, m: MemoryRecord) -> None:
        # Persist append-only to JSONL; we keep latest view in memory
        data = {
            "id": m.id,
            "question_seed": m.question_seed,
            "teaching_prompt": m.teaching_prompt,
            "teaching_type": m.teaching_type,
            "used_count": m.used_count,
            "success_count": m.success_count,
            "recommendation_score": m.recommendation_score,
            "attempts": m.attempts,
            "last_score": m.last_score,
            "updated_at": m.updated_at,
        }
        self.store.save_record(data)
        self.records[m.id] = m

    def _compute_embedding_hash(self, text: str) -> str:
        # Use the same encoder as VectorIndex; hashed embedding bytes for stable id
        # We do a tiny encode here to generate the id only once per new cluster
        emb = self.index.encoder.encode([text], convert_to_numpy=True)  # type: ignore
        b = emb.astype("float32").tobytes()
        return hashlib.sha256(b).hexdigest()[:16]

    def add_cluster(self, question_seed: str, teaching_prompt: str, teaching_type: str) -> MemoryRecord:
        rec_id = self._compute_embedding_hash(question_seed)
        if rec_id not in self.records:
            # Add to FAISS (index by question seed text)
            self.index.add_record(rec_id, question_seed)

        m = MemoryRecord(
            id=rec_id,
            question_seed=question_seed,
            teaching_prompt=teaching_prompt,
            teaching_type=teaching_type,
            used_count=0,
            success_count=0,
            recommendation_score=_reco_score(0, 0, DEFAULTS["recommendation"]["smoothing_num"], DEFAULTS["recommendation"]["smoothing_den"]),
            attempts=1,
            last_score=0.0,
            updated_at=_now_iso(),
        )
        self._save_record(m)
        return m

    def update_teaching(self, rec_id: str, teaching_prompt: str, teaching_type: Optional[str] = None) -> Optional[MemoryRecord]:
        m = self.records.get(rec_id)
        if not m:
            return None
        m.teaching_prompt = teaching_prompt
        if teaching_type:
            m.teaching_type = teaching_type
        m.attempts += 1
        m.updated_at = _now_iso()
        self._save_record(m)
        return m

    def credit_used(self, rec_id: str, success: bool, last_score: float) -> Optional[MemoryRecord]:
        m = self.records.get(rec_id)
        if not m:
            return None
        m.used_count += 1
        if success:
            m.success_count += 1
        m.last_score = last_score
        m.recommendation_score = _reco_score(
            m.success_count,
            m.used_count,
            DEFAULTS["recommendation"]["smoothing_num"],
            DEFAULTS["recommendation"]["smoothing_den"],
        )
        m.updated_at = _now_iso()
        self._save_record(m)
        return m

    def retrieve_similar(self, question: str, k: int) -> List[Tuple[str, float]]:
        # Returns list of (rec_id, similarity)
        results = self.index.retrieve_with_scores(question, k=k)
        return results

    def get_record(self, rec_id: str) -> Optional[MemoryRecord]:
        return self.records.get(rec_id)


# -----------------------------
# Dual-Score evaluation
# -----------------------------

def compute_d_score(pred: str, ref: str) -> Tuple[float, Dict[str, float]]:
    exact = det_metrics.exact_match(pred, ref)
    f1 = det_metrics.f1(pred, ref)
    bleu = det_metrics.bleu(pred, ref)
    w = DEFAULTS["d_weights"]
    overall = w["exact"] * exact + w["f1"] * f1 + w["bleu"] * bleu
    breakdown = {"exact": exact, "f1": f1, "bleu": bleu, "overall_d": overall}
    return overall, breakdown


def parse_float_first_line(text: str) -> Optional[float]:
    if text is None:
        return None
    line = str(text).strip().splitlines()[0].strip()
    try:
        val = float(line)
        if 0.0 <= val <= 1.0:
            return val
    except Exception:
        return None
    return None


def compute_t_score(
    question: str,
    student_answer: str,
    ground_truth: str,
    llm_client: Optional[Callable[[str, int], str]] = None,
) -> Optional[float]:
    if llm_client is None:
        return None
    prompt = _teacher_score_prompt(question, student_answer, ground_truth)
    try:
        out = llm_client(prompt, DEFAULTS["prompt"]["teacher_max_tokens"])
        score = parse_float_first_line(out)
        if score is None:
            logger.warning("Teacher score parse failed; falling back to deterministic score only")
        return score
    except Exception as e:
        logger.error(f"Teacher scoring error: {e}")
        return None


def aggregate_scores(d_score: float, t_score: Optional[float]) -> Tuple[float, Optional[float]]:
    a = DEFAULTS["agg"]
    if t_score is None:
        return d_score, None
    overall = a["d_weight"] * d_score + a["t_weight"] * float(t_score)
    disagreement = abs(d_score - float(t_score))
    return overall, disagreement


# -----------------------------
# Teaching generators
# -----------------------------

def generate_initial_teaching(
    question: str,
    student_answer: str,
    ground_truth: str,
    llm_client: Optional[Callable[[str, int], str]] = None,
) -> Tuple[str, str]:
    # Heuristic: short ground truth -> direct; else -> principle
    if _token_count(ground_truth) <= 4:
        return f"Answer: {ground_truth}", "direct"
    # Principle via LLM (fallback to a safe template if llm_client unavailable)
    if llm_client is None:
        return "Principle: Provide a concise, general method for solving this task.", "principle"
    prompt = _principle_prompt(question, student_answer, ground_truth)
    try:
        out = llm_client(prompt, DEFAULTS["prompt"]["teacher_max_tokens"])
        # Ensure it starts with 'Principle:'
        line = out.strip().splitlines()[0].strip()
        if not line.lower().startswith("principle:"):
            line = f"Principle: {line}"
        return line, "principle"
    except Exception:
        return "Principle: Provide a concise, general method for solving this task.", "principle"


def refine_teaching(
    prev_teaching: str,
    question: str,
    student_answer: str,
    ground_truth: str,
    llm_client: Optional[Callable[[str, int], str]] = None,
) -> str:
    if prev_teaching.lower().startswith("answer:"):
        # Direct answers generally don't need refinement; keep as-is
        return prev_teaching
    if llm_client is None:
        return prev_teaching
    prompt = _refine_principle_prompt(prev_teaching, question, student_answer, ground_truth)
    try:
        out = llm_client(prompt, DEFAULTS["prompt"]["teacher_max_tokens"])
        line = out.strip().splitlines()[0].strip()
        if not line.lower().startswith("principle:"):
            line = f"Principle: {line}"
        return line
    except Exception:
        return prev_teaching


# -----------------------------
# POC Orchestrator
# -----------------------------

class SimpleLoopPOC:
    def __init__(
        self,
        memory_dir: str = "logs/memory",
        embedding_model: str = "all-MiniLM-L6-v2",
    ) -> None:
        self.memory = MemoryManager(memory_dir=memory_dir, embedding_model=embedding_model)

    def _select_top_teaching(self, question: str) -> Optional[Tuple[str, MemoryRecord, float]]:
        cfg = DEFAULTS["retrieval"]
        results = self.memory.retrieve_similar(question, k=cfg["student_k"])  # List[(id, score)]
        # Filter by student threshold
        filtered: List[Tuple[str, float]] = [(rid, s) for rid, s in results if s >= cfg["student_threshold"]]
        if not filtered:
            return None
        # Rank by recommendation_score desc, then similarity desc, then recency
        candidates: List[Tuple[str, MemoryRecord, float]] = []
        for rid, sim in filtered:
            rec = self.memory.get_record(rid)
            if rec:
                candidates.append((rid, rec, float(sim)))
        if not candidates:
            return None
        candidates.sort(
            key=lambda x: (
                float(x[1].recommendation_score),
                float(x[2]),
                x[1].updated_at,
            ),
            reverse=True,
        )
        return candidates[0]

    def _dedup_window(self, question: str) -> Tuple[str, Optional[Tuple[str, MemoryRecord, float]]]:
        # Decide reuse/refine/new based on top-1 similarity window
        cfg = DEFAULTS["retrieval"]
        results = self.memory.retrieve_similar(question, k=1)
        if not results:
            return "new", None
        rid, sim = results[0]
        rec = self.memory.get_record(rid)
        if rec is None:
            return "new", None
        if sim >= cfg["reuse_threshold"]:
            return "reuse", (rid, rec, float(sim))
        if cfg["refine_lower"] <= sim < cfg["reuse_threshold"]:
            return "refine", (rid, rec, float(sim))
        return "new", None

    def run(
        self,
        question: str,
        ground_truth: str,
        student_client: Callable[[str, int], str],
        llm_client: Optional[Callable[[str, int], str]] = None,
        max_rounds: int = 3,
    ) -> Dict[str, Any]:
        history: List[Dict[str, Any]] = []
        selected_rec_id: Optional[str] = None

        for round_idx in range(1, max_rounds + 1):
            # Build prompt for student
            selection = self._select_top_teaching(question)
            if selection is not None:
                rid, rec, sim = selection
                selected_rec_id = rid
                hints = rec.teaching_prompt
                prompt = build_student_prompt(
                    question=question,
                    hints=hints,
                    context="",
                    use_cot=False,
                    previous_answer="" if round_idx == 1 else history[-1]["student_answer"],
                )
            else:
                selected_rec_id = None
                prompt = build_student_prompt(question=question, hints="", context="", use_cot=False, previous_answer="")

            # Ask student
            t0 = time.time()
            student_answer = student_client(prompt, DEFAULTS["prompt"]["student_max_tokens"])
            latency_ms = int((time.time() - t0) * 1000)

            # Evaluate
            d_score, breakdown = compute_d_score(student_answer, ground_truth)
            t_score = compute_t_score(question, student_answer, ground_truth, llm_client=llm_client)
            overall, disagreement = aggregate_scores(d_score, t_score)
            passed = overall >= DEFAULTS["agg"]["pass_threshold"]
            if (t_score is not None) and (disagreement is not None) and (
                disagreement > DEFAULTS["agg"]["disagreement_threshold"]
            ):
                logger.warning(
                    f"Score disagreement: d={d_score:.3f}, t={t_score:.3f}, diff={disagreement:.3f}"
                )

            # Update recommendation credit for selected teaching (used once regardless of pass/fail)
            if selected_rec_id is not None:
                self.memory.credit_used(selected_rec_id, success=passed, last_score=overall)

            # Record step
            history.append({
                "round": round_idx,
                "student_answer": student_answer,
                "d_score": d_score,
                "t_score": t_score,
                "overall": overall,
                "disagreement": disagreement,
                "latency_ms": latency_ms,
                "selected_rec_id": selected_rec_id,
            })

            if passed:
                return {
                    "success": True,
                    "num_rounds": round_idx,
                    "final_answer": student_answer,
                    "history": history,
                }

            # Not passed: update/refine/new teaching cluster
            decision, win = self._dedup_window(question)
            if decision == "reuse" and win is not None:
                # Do nothing special; keep current teaching
                pass
            elif decision == "refine" and win is not None:
                rid, rec, sim = win
                improved = refine_teaching(rec.teaching_prompt, question, student_answer, ground_truth, llm_client=llm_client)
                self.memory.update_teaching(rid, improved, teaching_type=rec.teaching_type)
            else:  # new cluster
                teaching_prompt, teaching_type = generate_initial_teaching(question, student_answer, ground_truth, llm_client=llm_client)
                self.memory.add_cluster(question_seed=question, teaching_prompt=teaching_prompt, teaching_type=teaching_type)

        # If loop ends without passing
        return {
            "success": False,
            "num_rounds": max_rounds,
            "final_answer": history[-1]["student_answer"] if history else "",
            "history": history,
        }


def build_student_client_tinyllama(
    model: str = "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
    temperature: float = 0.0,
    top_p: float = 1.0,
    timeout_s: int = 30,
):
    """
    Build a TinyLlama local student client and return a callable(prompt, max_tokens)->str.

    Notes:
    - Uses the repo's local provider (no API keys required).
    - Imports are done lazily to avoid heavy work at module import time.
    """
    # Import providers package to trigger provider registration via decorators
    import src.providers  # noqa: F401  (ensures local/gemini/groq modules register)
    from src.providers.factory import build_client  # lazy import

    student_provider = build_client(
        provider="local",
        model=model,
    )

    def _student_client(prompt: str, max_tokens: int = DEFAULTS["prompt"]["student_max_tokens"]) -> str:
        res = student_provider.chat(
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            timeout_s=timeout_s,
        )
        if getattr(res, "error", None):
            raise RuntimeError(f"Student error: {res.error}")
        return (res.text or "").strip()

    return _student_client


def build_teacher_client_gemini(
    model: str = "gemini-2.5-flash-lite",
    temperature: float = 0.1,
    top_p: float = 1.0,
    timeout_s: int = 30,
):
    """
    Build a Gemini teacher client and return a callable(prompt, max_tokens)->str.

    Notes:
    - Loads .env to ensure GOOGLE_API_KEY is present (via src.core.settings.load_env).
    - Rate limits are enforced automatically from src/providers/constants.py.
    - Imports are done lazily to avoid heavy work at module import time.
    """
    import os
    from src.core.settings import load_env  # lazy import
    # Import providers package to trigger provider registration via decorators
    import src.providers  # noqa: F401
    from src.providers.factory import build_client  # lazy import

    # Ensure env variables are loaded (GOOGLE_API_KEY)
    load_env()
    if not os.getenv("GOOGLE_API_KEY"):
        raise RuntimeError("GOOGLE_API_KEY not found. Add it to .env at repo root or environment.")

    teacher_provider = build_client(
        provider="gemini",
        model=model,
    )

    def _llm_client(prompt: str, max_tokens: int = DEFAULTS["prompt"]["teacher_max_tokens"]) -> str:
        res = teacher_provider.chat(
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            timeout_s=timeout_s,
        )
        if getattr(res, "error", None):
            raise RuntimeError(f"Teacher error: {res.error}")
        return (res.text or "").strip()

    return _llm_client


def build_default_clients():
    """Convenience helper returning (student_client, llm_client) with default models and settings."""
    return build_student_client_tinyllama(), build_teacher_client_gemini()


__all__ = [
    "SimpleLoopPOC",
    "MemoryRecord",
    "build_student_client_tinyllama",
    "build_teacher_client_gemini",
    "build_default_clients",
]


if __name__ == "__main__":
    # Minimal runnable harness for quick validation
    try:
        student_client, llm_client = build_default_clients()
        poc = SimpleLoopPOC(memory_dir="logs/memory", embedding_model="all-MiniLM-L6-v2")

        question = "Separate words: helloworld"
        ground_truth = "hello world"

        res = poc.run(
            question=question,
            ground_truth=ground_truth,
            student_client=student_client,
            llm_client=llm_client,
            max_rounds=3,
        )
        print(json.dumps({
            "success": res.get("success"),
            "num_rounds": res.get("num_rounds"),
            "final_answer": res.get("final_answer"),
        }, ensure_ascii=False, indent=2))
    except Exception as e:
        logger.error(f"POC run failed: {e}")
        print("Hint: ensure dependencies installed (faiss, sentence-transformers, transformers, torch, google-genai)")
        print("Hint: ensure GOOGLE_API_KEY is set in .env at project root for Gemini teacher")

"""FaissMemory — slot D 'faiss' backend (schema.md Memory v2 contract).

Salvaged from `src/simplified/memory.py` (FAISS handling, IndexFlatIP over
normalized MiniLM vectors, JSONL-for-inspection persistence, success-aware
ranking) 's Read-first list — rewritten lean around the v2 episode
schema and a hard store-time tripwire (`tripwire.py`). `src/simplified/memory.py`
is untouched (frozen legacy, structure.md §E).

Contract this satisfies: schema.md "Memory v2 contract" §1 (episode schema),
§2 (tripwire), §3 (retrieval), §4 (MemoryBackend interface), §5 (lifecycle:
per-run isolation, eviction, update flow).
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from src.tlw.memory.tripwire import run_tripwire
from src.tlw.registries import MEMORY_REGISTRY, MemoryBackend

_DEFAULT_EMBEDDING = "minilm"
_ENCODER_NAMES = {"minilm": "all-MiniLM-L6-v2"}


def _now() -> str:
    return datetime.now().isoformat()


def _blank_stats() -> Dict[str, Any]:
    return {
        "attempts": 0,
        "success_count": 0,
        "success_rate": 0.0,
        "best_final_score": 0.0,
    }


@MEMORY_REGISTRY.register("faiss")
class FaissMemory(MemoryBackend):
    """Per-run FAISS-backed teaching-note store. NOT thread/process safe
    (deliberately single-user/single-machine, Must-NOT — no prod scale)."""

    def __init__(
        self,
        storage_dir: str,
        embedding: str = _DEFAULT_EMBEDDING,
        top_k: int = 3,
        similarity_threshold: float = 0.75,
        min_success_rate: float = 0.30,
        max_episodes: int = 1000,
        gt_substring_shingle: int = 12,
        gt_similarity_max: float = 0.80,
        seed_from: Optional[str] = None,
        **_ignored: Any,
    ):
        if not storage_dir:
            raise ValueError(
                "FaissMemory requires storage_dir (per-run isolated path, "
                "Memory v2 contract §5) — the runner must derive it from run_id."
            )
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self.embedding = embedding
        self._encoder_name = _ENCODER_NAMES.get(embedding, embedding)
        self.top_k = top_k
        self.similarity_threshold = similarity_threshold
        self.min_success_rate = min_success_rate
        self.max_episodes = max_episodes
        self.gt_substring_shingle = gt_substring_shingle
        self.gt_similarity_max = gt_similarity_max

        self.episodes_path = self.storage_dir / "memory_episodes.jsonl"
        self.index_path = self.storage_dir / "faiss.index"
        self.ids_path = self.storage_dir / "faiss.ids.json"
        self.rejects_path = self.storage_dir / "memory_rejects.jsonl"

        self._encoder = None
        self._index = None
        self._id_to_record: Dict[str, Dict[str, Any]] = {}
        self._ids: List[str] = []
        self._rejects = 0

        # Fresh empty store by default (§5 per-run isolation). Loading only
        # happens from THIS storage_dir (reload of a prior run of the SAME
        # experiment), never implicitly from another run's directory.
        self._load_from_disk()

        if seed_from:
            self._seed_from(seed_from)

    # --- lazy heavy deps (mirrors legacy memory.py) ---

    @property
    def encoder(self):
        if self._encoder is None:
            from sentence_transformers import SentenceTransformer

            self._encoder = SentenceTransformer(self._encoder_name)
        return self._encoder

    @property
    def index(self):
        # Always rebuilt from `_id_to_record` question embeddings (never
        # loaded from `index_path` directly) — the persisted .index/.ids.json
        # trio is for external inspection (schema.md storage map), not the
        # in-memory source of truth, so a load followed by a rebuild can never
        # double-add vectors.
        if self._index is None:
            import faiss

            dim = self.encoder.encode(["test"]).shape[1]
            self._index = faiss.IndexFlatIP(dim)
        return self._index

    def _embed(self, text: str) -> np.ndarray:
        emb = self.encoder.encode([text], convert_to_numpy=True)[0]
        norm = np.linalg.norm(emb)
        if norm > 0:
            emb = emb / norm
        return emb.astype("float32")

    def _cosine(self, a: str, b: str) -> float:
        ea, eb = self._embed(a), self._embed(b)
        return float(np.dot(ea, eb))

    def _generate_id(self, question: str) -> str:
        emb = self._embed(question)
        return hashlib.sha256(emb.tobytes()).hexdigest()[:16]

    # --- persistence ---

    def _load_from_disk(self) -> None:
        if not self.episodes_path.exists():
            return
        with open(self.episodes_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                self._id_to_record[record["id"]] = record
                if record["id"] not in self._ids:
                    self._ids.append(record["id"])
        if self._id_to_record:
            embeddings = [self._embed(self._id_to_record[rid]["question"]) for rid in self._ids]
            embeddings = np.array(embeddings).astype("float32")
            self.index.add(embeddings)
        if self.rejects_path.exists():
            with open(self.rejects_path, "r", encoding="utf-8") as f:
                self._rejects = sum(1 for line in f if line.strip())

    def _save_episodes(self) -> None:
        with open(self.episodes_path, "w", encoding="utf-8") as f:
            for rid in self._ids:
                f.write(json.dumps(self._id_to_record[rid], ensure_ascii=False) + "\n")

    def _save_index(self) -> None:
        import faiss

        faiss.write_index(self.index, str(self.index_path))
        with open(self.ids_path, "w", encoding="utf-8") as f:
            json.dump(self._ids, f, indent=2)

    def _log_reject(self, reason: str, run_id: Optional[str], question_id: Optional[str], note: str) -> None:
        # Never log the note or GT text itself (§2) — only a hash + metadata.
        note_hash = hashlib.sha256((note or "").encode("utf-8")).hexdigest()[:16]
        entry = {
            "event": "memory_reject",
            "reason": reason,
            "run_id": run_id,
            "question_id": question_id,
            "note_hash": note_hash,
            "timestamp": _now(),
        }
        with open(self.rejects_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        self._rejects += 1

    def _seed_from(self, seed_from: str) -> None:
        """Copy episodes from another store's episodes.jsonl into this fresh
        store (Memory v2 contract §5). Denylist is enforced by the config
        loader (V6); this is defense-in-depth for direct construction."""
        from src.tlw.config.schema import MEMORY_PATH_DENYLIST

        lowered = str(seed_from).replace("\\", "/").lower()
        for bad in MEMORY_PATH_DENYLIST:
            if bad in lowered:
                raise ValueError(
                    f"seed_from '{seed_from}' matches denylisted term '{bad}' "
                    "(Config Contract V6, LEAKAGE_AUDIT seal #6) — refusing to seed."
                )
        seed_path = Path(seed_from)
        if not seed_path.exists():
            raise FileNotFoundError(f"seed_from path does not exist: {seed_from}")
        with open(seed_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                if record["id"] in self._id_to_record:
                    continue
                self._id_to_record[record["id"]] = record
                self._ids.append(record["id"])
                self.index.add(self._embed(record["question"]).reshape(1, -1))
        self._save_episodes()
        self._save_index()

    # --- MemoryBackend interface ---

    def store(
        self, episode: Dict[str, Any], reference_answer: Optional[str] = None
    ) -> Optional[str]:
        question = episode.get("question")
        note = episode.get("teaching_note", "")
        if not question:
            raise ValueError("episode.question is required")

        cosine_sim = None
        if reference_answer:
            cosine_sim = self._cosine(note, reference_answer)

        result = run_tripwire(
            note,
            reference_answer,
            cosine_sim,
            gt_substring_shingle=self.gt_substring_shingle,
            gt_similarity_max=self.gt_similarity_max,
        )
        if result.rejected:
            provenance = episode.get("provenance") or {}
            self._log_reject(
                result.reason,
                run_id=provenance.get("run_id"),
                question_id=episode.get("id"),
                note=note,
            )
            return None

        record_id = self._generate_id(question)
        now = _now()
        incoming_stats = {**_blank_stats(), **(episode.get("stats") or {})}

        if record_id in self._id_to_record:
            record = self._id_to_record[record_id]
            old_best = record["stats"].get("best_final_score", 0.0)
            record["stats"]["attempts"] += incoming_stats.get("attempts", 0) or 1
            if incoming_stats.get("success_count"):
                record["stats"]["success_count"] += incoming_stats["success_count"]
            if record["stats"]["attempts"] > 0:
                record["stats"]["success_rate"] = (
                    record["stats"]["success_count"] / record["stats"]["attempts"]
                )
            new_best = incoming_stats.get("best_final_score", 0.0)
            if new_best > old_best:
                record["teaching_note"] = note
                record["stats"]["best_final_score"] = new_best
                record["tags"] = episode.get("tags", record.get("tags", []))
                record["links"] = episode.get("links", record.get("links", []))
            record["provenance"]["updated"] = now
        else:
            record = {
                "id": record_id,
                "question": question,
                "embedding_key": f"{self.embedding}/{record_id}",
                "teaching_note": note,
                "tags": episode.get("tags", []),
                "links": episode.get("links", []),
                "stats": {
                    "attempts": incoming_stats.get("attempts", 0) or 1,
                    "success_count": incoming_stats.get("success_count", 0),
                    "success_rate": incoming_stats.get("success_rate", 0.0),
                    "best_final_score": incoming_stats.get("best_final_score", 0.0),
                },
                "provenance": {
                    "run_id": (episode.get("provenance") or {}).get("run_id"),
                    "arm": (episode.get("provenance") or {}).get("arm"),
                    "teacher_model": (episode.get("provenance") or {}).get("teacher_model"),
                    "created": now,
                    "updated": now,
                },
            }
            self._id_to_record[record_id] = record
            self._ids.append(record_id)
            self.index.add(self._embed(question).reshape(1, -1).astype("float32"))

        self._save_episodes()
        self._save_index()
        self._evict_if_over_capacity()
        return record_id

    def retrieve(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        k = top_k if top_k is not None else self.top_k
        if k <= 0 or self.index.ntotal == 0:
            return []

        query_emb = self._embed(query).reshape(1, -1)
        scores, indices = self.index.search(query_emb, min(k, self.index.ntotal))

        candidates = []
        for idx, sim in zip(indices[0], scores[0]):
            if idx < 0 or idx >= len(self._ids):
                continue
            if sim < self.similarity_threshold:
                continue
            record = self._id_to_record[self._ids[idx]]
            if record["stats"].get("success_rate", 0.0) < self.min_success_rate:
                continue
            candidates.append((record, float(sim)))

        candidates.sort(
            key=lambda pair: (
                pair[0]["stats"].get("success_rate", 0.0),
                pair[0]["stats"].get("best_final_score", 0.0),
                pair[0]["stats"].get("attempts", 0),
                pair[1],
            ),
            reverse=True,
        )

        return [
            {
                "id": record["id"],
                "teaching_note": record["teaching_note"],
                "success_rate": record["stats"].get("success_rate", 0.0),
                "best_final_score": record["stats"].get("best_final_score", 0.0),
                "attempts": record["stats"].get("attempts", 0),
                "similarity": sim,
            }
            for record, sim in candidates[:k]
        ]

    def update_outcome(self, episode_id: str, scores: Dict[str, float]) -> None:
        record = self._id_to_record.get(episode_id)
        if record is None:
            return
        success = bool(scores.get("success"))
        record["stats"]["attempts"] += 1
        if success:
            record["stats"]["success_count"] += 1
        if record["stats"]["attempts"] > 0:
            record["stats"]["success_rate"] = (
                record["stats"]["success_count"] / record["stats"]["attempts"]
            )
        final_score = scores.get("final_score")
        if final_score is not None and final_score > record["stats"].get("best_final_score", 0.0):
            record["stats"]["best_final_score"] = final_score
        record["provenance"]["updated"] = _now()
        self._save_episodes()

    def stats(self) -> Dict[str, Any]:
        total_episodes = len(self._id_to_record)
        total_attempts = sum(r["stats"]["attempts"] for r in self._id_to_record.values())
        total_successes = sum(r["stats"]["success_count"] for r in self._id_to_record.values())
        return {
            "total_episodes": total_episodes,
            "total_attempts": total_attempts,
            "overall_success_rate": (total_successes / total_attempts) if total_attempts else 0.0,
            "index_size": self.index.ntotal if self._index is not None else 0,
            "rejects": self._rejects,
        }

    # --- lifecycle: capacity/eviction (§5) ---

    def _evict_if_over_capacity(self) -> None:
        if self.max_episodes is None or len(self._id_to_record) <= self.max_episodes:
            return
        overflow = len(self._id_to_record) - self.max_episodes
        ranked = sorted(
            self._ids,
            key=lambda rid: (
                self._id_to_record[rid]["stats"].get("success_rate", 0.0),
                self._id_to_record[rid]["stats"].get("attempts", 0),
            ),
        )
        to_evict = set(ranked[:overflow])
        self._ids = [rid for rid in self._ids if rid not in to_evict]
        for rid in to_evict:
            del self._id_to_record[rid]
        self._rebuild_index()
        self._save_episodes()
        self._save_index()

    def _rebuild_index(self) -> None:
        import faiss

        dim = self.encoder.encode(["test"]).shape[1]
        self._index = faiss.IndexFlatIP(dim)
        if self._ids:
            embeddings = np.array(
                [self._embed(self._id_to_record[rid]["question"]) for rid in self._ids]
            ).astype("float32")
            self._index.add(embeddings)

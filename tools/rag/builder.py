"""RAG retrieval-corpus + FAISS index builder (T3.2, RAG_SPEC §1 / §5).

Turns a cleaned Q&A jsonl into a retrieval index: one passage per record
(v1, no sub-chunking — RAG_SPEC §1.1), keyed by the record QUESTION embedding,
returning the record ANSWER as the grounding passage. Reuses:
  - the project MiniLM encoder via `tools.dataset.embeddings.embed` (normalized)
  - the FAISS IndexFlatIP construction from `src/tlw/memory/faiss_backend.py`

Honesty seals enforced at build time (RAG_SPEC §5, schema.md slot-D `rag`):
  RAG-L1  held-out records provably excluded (by id) — manifest records the check.
  RAG-L2  drop any source record whose QUESTION or ANSWER is >= dedup_threshold
          cosine (MiniLM, default 0.90 = rubric D3) to any held-out record — an
          answer-key-by-proxy scrub (uniqueness is 97.3, not 100).
Plus a defensive text check: no held-out answer text may appear verbatim as an
indexed passage.

Output (all under a NON-immutable dir, default indexes/<name>/):
  faiss.index      binary FAISS IndexFlatIP over question embeddings (row order)
  passages.jsonl   one line per FAISS row (row order == index order): the passage store
  faiss.ids.json   [passage_id, ...] in row order (external inspection, mirrors faiss_backend)
  manifest.json    machine-readable build record incl. the exclusion checks
  build_report.md  human report incl. sample retrievals
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from collections import Counter, defaultdict

import numpy as np

from tools.dataset.embeddings import embed
from src.tlw.evaluation.diagnostics import normalize_text

_DEFAULT_ENCODER = "all-MiniLM-L6-v2"
_EMBEDDING_NAME = "minilm"  # slot-D key name (schema.md); maps to the encoder above
_SHINGLE_N = 12  # verbatim-block unit; MUST match the loop guard (core.py _MIN_SHINGLE_TOKENS)


def _shingles(tokens, n: int = _SHINGLE_N):
    if len(tokens) < n:
        return set()
    return {" ".join(tokens[i : i + n]) for i in range(len(tokens) - n + 1)}


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


@dataclass
class BuildReport:
    """Machine-readable outcome of one build (also serialized to manifest.json)."""

    name: str
    source: str
    exclude: Optional[str]
    embedding: str
    encoder: str
    dim: int
    index_type: str
    dedup_threshold: float
    block_shingle_min: int
    n_source: int
    n_dropped_heldout_id: int
    n_dropped_near_dup: int
    n_dropped_block: int
    n_indexed: int
    heldout_id_exclusion: str  # "PASS" / "FAIL: ..."
    heldout_text_exclusion: str
    dropped_near_dup_ids: List[str] = field(default_factory=list)
    dropped_block_ids: List[str] = field(default_factory=list)
    sample_retrievals: List[Dict[str, Any]] = field(default_factory=list)
    created: str = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items()}


class RagIndexBuilder:
    """Build a retrieval index from a cleaned jsonl. Domain-agnostic."""

    def __init__(
        self,
        source: str,
        out_dir: str,
        exclude: Optional[str] = None,
        name: Optional[str] = None,
        dedup_threshold: float = 0.90,
        block_shingle_min: int = 8,
        question_field: str = "question",
        answer_field: str = "answer",
        id_field: str = "id",
    ):
        self.source_path = Path(source)
        self.exclude_path = Path(exclude) if exclude else None
        self.out_dir = Path(out_dir)
        self.name = name or self.source_path.stem
        self.dedup_threshold = dedup_threshold
        self.block_shingle_min = block_shingle_min
        self.qf = question_field
        self.af = answer_field
        self.idf = id_field

        if not self.source_path.exists():
            raise FileNotFoundError(f"source not found: {self.source_path}")
        if self.exclude_path and not self.exclude_path.exists():
            raise FileNotFoundError(f"exclude not found: {self.exclude_path}")

    # --- build ---

    def build(self) -> BuildReport:
        source = _read_jsonl(self.source_path)
        n_source = len(source)
        exclude = _read_jsonl(self.exclude_path) if self.exclude_path else []

        held_ids = {r.get(self.idf) for r in exclude}
        held_questions = [r.get(self.qf, "") for r in exclude]
        held_answers = [r.get(self.af, "") for r in exclude]

        # RAG-L1: drop any source record whose id is a held-out id.
        after_l1 = [r for r in source if r.get(self.idf) not in held_ids]
        n_dropped_id = n_source - len(after_l1)

        # RAG-L2: near-duplicate scrub against held-out. Two complementary
        # filters (RAG_SPEC §5, strengthened per the 2026-07-16 hub finding —
        # whole-answer cosine alone misses templated answers that share a large
        # VERBATIM block while differing overall, e.g. the "What to do for
        # Crohn's" vs "…Ulcerative Colitis" NIH template, cosine 0.76 but ~100%
        # shared text):
        #   (a) cosine >= dedup_threshold on question OR answer (semantic twin)
        #   (b) shares >= block_shingle_min contiguous 12-token shingles with any
        #       held-out ANSWER (verbatim-block / template twin)
        kept, dropped_near_dup_ids, dropped_block_ids = self._scrub_near_dups(
            after_l1, held_questions, held_answers
        )
        n_dropped_near_dup = len(dropped_near_dup_ids)
        n_dropped_block = len(dropped_block_ids)

        # Build passages (one per surviving record) + question-keyed index.
        passages = self._to_passages(kept)
        index, ids = self._build_index(passages)

        # Exclusion checks (RAG-L1 hard verification for the manifest).
        indexed_ids = {p["id"] for p in passages}
        id_overlap = indexed_ids & held_ids
        heldout_id_exclusion = (
            "PASS" if not id_overlap else f"FAIL: {len(id_overlap)} held-out ids indexed"
        )
        heldout_text_exclusion = self._verify_no_heldout_text(passages, held_answers)

        report = BuildReport(
            name=self.name,
            source=str(self.source_path),
            exclude=str(self.exclude_path) if self.exclude_path else None,
            embedding=_EMBEDDING_NAME,
            encoder=_DEFAULT_ENCODER,
            dim=index.d,
            index_type="IndexFlatIP",
            dedup_threshold=self.dedup_threshold,
            block_shingle_min=self.block_shingle_min,
            n_source=n_source,
            n_dropped_heldout_id=n_dropped_id,
            n_dropped_near_dup=n_dropped_near_dup,
            n_dropped_block=n_dropped_block,
            n_indexed=len(passages),
            heldout_id_exclusion=heldout_id_exclusion,
            heldout_text_exclusion=heldout_text_exclusion,
            dropped_near_dup_ids=dropped_near_dup_ids,
            dropped_block_ids=dropped_block_ids,
        )

        self._persist(index, passages, ids, report)
        report.sample_retrievals = self._sample_retrievals(
            index, passages, held_questions or [p["question"] for p in passages[:3]]
        )
        self._write_report(report)
        # rewrite manifest with sample retrievals included
        self._write_manifest(report)
        return report

    # --- steps ---

    def _scrub_near_dups(
        self,
        records: List[Dict[str, Any]],
        held_questions: List[str],
        held_answers: List[str],
    ) -> tuple[List[Dict[str, Any]], List[str], List[str]]:
        if not held_questions:
            return records, [], []

        src_q = embed([r.get(self.qf, "") for r in records])  # (n, d) normalized
        src_a = embed([r.get(self.af, "") for r in records])
        held_q = embed(held_questions)
        held_a = embed(held_answers)

        # (a) semantic twin: max cosine of each source record vs ANY held-out.
        max_q = (src_q @ held_q.T).max(axis=1)
        max_a = (src_a @ held_a.T).max(axis=1)

        # (b) verbatim-block twin: inverted index of held-out answer 12-shingles
        # -> which held-out docs contain each shingle; then for each source
        # answer, the MAX shared-shingle count against any single held-out doc.
        held_index: defaultdict = defaultdict(set)
        for hi, ha in enumerate(held_answers):
            for sh in _shingles(normalize_text(ha).split()):
                held_index[sh].add(hi)

        def max_block_overlap(answer: str) -> int:
            counts: Counter = Counter()
            for sh in _shingles(normalize_text(answer).split()):
                for hi in held_index.get(sh, ()):  # type: ignore[arg-type]
                    counts[hi] += 1
            return max(counts.values()) if counts else 0

        kept: List[Dict[str, Any]] = []
        dropped_cosine: List[str] = []
        dropped_block: List[str] = []
        for i, rec in enumerate(records):
            rid = str(rec.get(self.idf))
            if max_q[i] >= self.dedup_threshold or max_a[i] >= self.dedup_threshold:
                dropped_cosine.append(rid)
            elif max_block_overlap(rec.get(self.af, "")) >= self.block_shingle_min:
                dropped_block.append(rid)
            else:
                kept.append(rec)
        return kept, dropped_cosine, dropped_block

    def _to_passages(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        passages: List[Dict[str, Any]] = []
        for row, rec in enumerate(records):
            answer = (rec.get(self.af) or "").strip()
            question = (rec.get(self.qf) or "").strip()
            if not answer or not question:
                continue
            passages.append(
                {
                    "row": len(passages),
                    "id": rec.get(self.idf),
                    "question": question,
                    "passage": answer,
                    "domain": rec.get("domain"),
                    "source_id": rec.get(self.idf),
                    "word_len": len(answer.split()),
                }
            )
        # re-number rows after any skips so row == list index
        for i, p in enumerate(passages):
            p["row"] = i
        return passages

    def _build_index(self, passages: List[Dict[str, Any]]):
        import faiss

        questions = [p["question"] for p in passages]
        vecs = embed(questions)  # (n, d) L2-normalized
        dim = int(vecs.shape[1])
        index = faiss.IndexFlatIP(dim)
        index.add(vecs.astype("float32"))
        ids = [p["id"] for p in passages]
        return index, ids

    def _verify_no_heldout_text(
        self, passages: List[Dict[str, Any]], held_answers: List[str]
    ) -> str:
        if not held_answers:
            return "N/A (no exclude file)"
        held_norm = {" ".join(a.split()).lower() for a in held_answers if a}
        for p in passages:
            if " ".join(p["passage"].split()).lower() in held_norm:
                return f"FAIL: passage id={p['id']} equals a held-out answer"
        return "PASS"

    # --- persistence ---

    def _persist(self, index, passages, ids, report: BuildReport) -> None:
        import faiss

        self.out_dir.mkdir(parents=True, exist_ok=True)
        faiss.write_index(index, str(self.out_dir / "faiss.index"))
        with open(self.out_dir / "passages.jsonl", "w", encoding="utf-8") as f:
            for p in passages:
                f.write(json.dumps(p, ensure_ascii=False) + "\n")
        with open(self.out_dir / "faiss.ids.json", "w", encoding="utf-8") as f:
            json.dump(ids, f, indent=2)
        self._write_manifest(report)

    def _write_manifest(self, report: BuildReport) -> None:
        with open(self.out_dir / "manifest.json", "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, indent=2, ensure_ascii=False)

    def _sample_retrievals(
        self, index, passages: List[Dict[str, Any]], queries: List[str], k: int = 3, n_q: int = 3
    ) -> List[Dict[str, Any]]:
        """Eyeball-quality demo (RAG_SPEC/T3.2 step 3). Queries are for DISPLAY
        only — nothing is tuned against them (Must-NOT: no hand-tuning vs heldout)."""
        if not passages:
            return []
        picks = queries[:n_q]
        qvecs = embed(picks)
        scores, idxs = index.search(qvecs.astype("float32"), min(k, len(passages)))
        out: List[Dict[str, Any]] = []
        for qi, query in enumerate(picks):
            hits = []
            for rank, (row, sim) in enumerate(zip(idxs[qi], scores[qi])):
                if row < 0:
                    continue
                p = passages[int(row)]
                hits.append(
                    {
                        "rank": rank + 1,
                        "similarity": round(float(sim), 4),
                        "matched_question": p["question"],
                        "passage_preview": p["passage"][:200],
                    }
                )
            out.append({"query": query, "top_k": hits})
        return out

    def _write_report(self, report: BuildReport) -> None:
        r = report
        lines: List[str] = []
        lines.append(f"# RAG Index Build Report — {r.name}")
        lines.append("")
        lines.append(f"*Built {r.created} · reproducible: `python -m tools.rag.cli` (§0.3)*")
        lines.append("")
        lines.append("| field | value |")
        lines.append("|---|---|")
        lines.append(f"| source | `{r.source}` |")
        lines.append(f"| exclude (held-out) | `{r.exclude}` |")
        lines.append(f"| embedding | {r.embedding} (`{r.encoder}`), dim {r.dim} |")
        lines.append(f"| index | {r.index_type} (cosine / inner-product) |")
        lines.append(f"| source records | {r.n_source} |")
        lines.append(f"| dropped — held-out id (RAG-L1) | {r.n_dropped_heldout_id} |")
        lines.append(
            f"| dropped — cosine >= {r.dedup_threshold} vs held-out (RAG-L2a) | {r.n_dropped_near_dup} |"
        )
        lines.append(
            f"| dropped — verbatim-block >= {r.block_shingle_min} shingles vs held-out (RAG-L2b) | {r.n_dropped_block} |"
        )
        lines.append(f"| **indexed passages** | **{r.n_indexed}** |")
        lines.append("")
        lines.append("## Honesty seals (RAG_SPEC §5)")
        lines.append("")
        lines.append(f"- **Held-out id exclusion (RAG-L1):** {r.heldout_id_exclusion}")
        lines.append(f"- **Held-out verbatim-text exclusion:** {r.heldout_text_exclusion}")
        lines.append(
            f"- **Cosine near-dup scrub (RAG-L2a):** dropped {r.n_dropped_near_dup} source records "
            f"within {r.dedup_threshold} cosine of a held-out record "
            f"(ids: {', '.join(r.dropped_near_dup_ids) if r.dropped_near_dup_ids else 'none'})"
        )
        lines.append(
            f"- **Verbatim-block scrub (RAG-L2b):** dropped {r.n_dropped_block} source records "
            f"sharing >= {r.block_shingle_min} twelve-token shingles with a held-out answer "
            f"(templated answer-by-proxy leaks; ids: "
            f"{', '.join(r.dropped_block_ids) if r.dropped_block_ids else 'none'})"
        )
        lines.append("")
        lines.append("## Sample retrievals (eyeball only — no tuning against these)")
        lines.append("")
        for s in r.sample_retrievals:
            lines.append(f"**Query:** {s['query']}")
            lines.append("")
            for h in s["top_k"]:
                lines.append(
                    f"- [{h['rank']}] sim={h['similarity']} — *{h['matched_question']}*"
                )
                lines.append(f"  > {h['passage_preview']}…")
            lines.append("")
        with open(self.out_dir / "build_report.md", "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

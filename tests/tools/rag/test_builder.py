"""RAG index builder tests — the held-out-exclusion seals are the point.

Uses the real MiniLM encoder (same as tests/tlw/memory) on a tiny synthetic
corpus, so the near-dup scrub is exercised against actual cosine values.
"""

import json
from pathlib import Path

import pytest

from tools.rag.builder import RagIndexBuilder


def _write_jsonl(path: Path, records):
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


@pytest.fixture
def corpus(tmp_path):
    """A 5-record train split + a 2-record held-out split.

    train t-dup shares an ANSWER with a held-out record (near-dup, must scrub);
    train t-idclash shares an ID with a held-out record (RAG-L1, must drop).
    """
    train = [
        {"id": "t-1", "domain": "d", "question": "What is diabetes?",
         "answer": "Diabetes is a disease where blood glucose is too high over time."},
        {"id": "t-2", "domain": "d", "question": "What causes kidney stones?",
         "answer": "Kidney stones form when urine minerals crystallize into solid pieces."},
        {"id": "t-3", "domain": "d", "question": "What are ulcer symptoms?",
         "answer": "A burning stomach pain is the most common symptom of a peptic ulcer."},
        {"id": "t-dup", "domain": "d", "question": "Define hypoglycemia please",
         "answer": "Hypoglycemia means abnormally low blood sugar, often from too much insulin."},
        {"id": "h-1", "domain": "d", "question": "id clash record",
         "answer": "This train record collides on id with a held-out record."},
    ]
    held = [
        {"id": "h-1", "domain": "d", "question": "What is hypertension?",
         "answer": "Hypertension is persistently high blood pressure in the arteries."},
        {"id": "h-2", "domain": "d", "question": "What is hypoglycemia?",
         "answer": "Hypoglycemia means abnormally low blood sugar, often from too much insulin."},
    ]
    tp = tmp_path / "train.jsonl"
    hp = tmp_path / "held.jsonl"
    _write_jsonl(tp, train)
    _write_jsonl(hp, held)
    return tp, hp, tmp_path


def test_heldout_id_excluded(corpus):
    tp, hp, root = corpus
    report = RagIndexBuilder(str(tp), str(root / "out"), exclude=str(hp)).build()
    # t-idclash shares id "h-1" with a held-out record -> dropped by RAG-L1.
    assert report.n_dropped_heldout_id == 1
    assert report.heldout_id_exclusion == "PASS"
    ids = json.loads((root / "out" / "faiss.ids.json").read_text())
    assert "h-1" not in ids


def test_near_dup_answer_scrubbed(corpus):
    tp, hp, root = corpus
    report = RagIndexBuilder(str(tp), str(root / "out"), exclude=str(hp)).build()
    # t-dup answer is verbatim-equal to held-out h-2's answer -> RAG-L2 (cos=1.0).
    assert report.n_dropped_near_dup >= 1
    assert "t-dup" in report.dropped_near_dup_ids
    assert report.heldout_text_exclusion == "PASS"  # scrub ran before the text check


def test_indexed_passages_survive(corpus):
    tp, hp, root = corpus
    report = RagIndexBuilder(str(tp), str(root / "out"), exclude=str(hp)).build()
    passages = [json.loads(l) for l in (root / "out" / "passages.jsonl").read_text().splitlines()]
    kept_ids = {p["id"] for p in passages}
    # clean, non-colliding, non-dup records remain
    assert {"t-1", "t-2", "t-3"} <= kept_ids
    # scrubbed/clashing records gone
    assert "t-dup" not in kept_ids
    assert report.n_indexed == len(passages)
    # every passage carries answer-as-text + question-as-key metadata
    for p in passages:
        assert p["passage"] and p["question"] and p["id"]


def test_retrieval_returns_relevant_passage(corpus):
    tp, hp, root = corpus
    RagIndexBuilder(str(tp), str(root / "out"), exclude=str(hp)).build()
    import faiss
    from tools.dataset.embeddings import embed

    index = faiss.read_index(str(root / "out" / "faiss.index"))
    passages = [json.loads(l) for l in (root / "out" / "passages.jsonl").read_text().splitlines()]
    q = embed(["What is diabetes mellitus?"]).astype("float32")
    scores, idxs = index.search(q, 1)
    top = passages[int(idxs[0][0])]
    assert "diabetes" in top["passage"].lower()


def test_no_exclude_file_is_generality_smoke(corpus):
    """Domain-agnostic: builds with no held-out file (a split-less domain)."""
    tp, hp, root = corpus
    report = RagIndexBuilder(str(tp), str(root / "out2"), exclude=None).build()
    assert report.n_indexed == 5  # nothing dropped without an exclude set
    assert report.n_dropped_near_dup == 0
    assert report.n_dropped_block == 0
    assert report.heldout_id_exclusion == "PASS"
    assert report.heldout_text_exclusion.startswith("N/A")


def test_verbatim_block_scrub_catches_template_twin(tmp_path):
    """RAG-L2b: a train record whose answer embeds a large VERBATIM block copied
    from a held-out answer (but whole-doc cosine < 0.90, so RAG-L2a misses it —
    the real "What to do for Crohn's" vs "…Ulcerative Colitis" template case) is
    dropped by the block scrub. Uses block_shingle_min=2 for the tiny fixture."""
    shared = (
        "avoiding carbonated drinks avoiding popcorn vegetable skins nuts and other "
        "high fiber foods while symptoms flare up during treatment"
    )  # 20-token block -> shares shingles when copied verbatim
    held = [
        {"id": "h-1", "domain": "d", "question": "What to do for Crohn's Disease?",
         "answer": f"Good nutrition helps manage Crohn's disease. A provider may recommend {shared}."},
    ]
    # A DIFFERENT-topic train answer that nonetheless copies the shared block:
    train = [
        {"id": "t-liver", "domain": "d", "question": "What is cirrhosis of the liver?",
         "answer": (
             "Cirrhosis is late-stage scarring of the liver caused by many forms of liver "
             "disease such as hepatitis and chronic alcohol use over a long period of time. "
             f"For unrelated dietary notes a provider may recommend {shared}."
         )},
        {"id": "t-clean", "domain": "d", "question": "What are gallstones?",
         "answer": "Gallstones are hardened deposits of digestive fluid that form in the gallbladder."},
    ]
    tp, hp = tmp_path / "t.jsonl", tmp_path / "h.jsonl"
    _write_jsonl(tp, train)
    _write_jsonl(hp, held)
    report = RagIndexBuilder(str(tp), str(tmp_path / "out"), exclude=str(hp), block_shingle_min=2).build()
    # t-liver copied a verbatim block from the held-out answer -> block-scrubbed,
    # even though it is about a different organ (cosine well under 0.90).
    assert "t-liver" in report.dropped_block_ids
    assert "t-liver" not in report.dropped_near_dup_ids  # NOT a cosine twin
    assert "t-clean" not in report.dropped_block_ids  # unrelated record survives

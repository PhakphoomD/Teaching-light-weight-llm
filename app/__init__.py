"""Local WixQA RAG engine — generates the before/after comparison evidence.

`engine.py` is the pure-Python core (retrieval + grounding narrow/wide + answer via a
local 3B); `build_showcase.py` uses it to capture the curated before/after examples in
`reports/rag-wixqa/demo-showcase.jsonl`, which the results tables present. A
Streamlit UI was prototyped and removed (generic; low differentiation). See `app/README.md`.
"""

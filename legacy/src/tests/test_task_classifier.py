import pytest

from src.memory.plugins.task_classifier import (
    pre_normalize,
    extract_task_type,
)


def test_pre_normalize_keeps_math_symbols():
    s = "Compute 2 + 3 * (4 - 1) / 2 = 9%^2?"
    out = pre_normalize(s)
    for ch in "+-*/%()=^":
        assert ch in out, f"Missing '{ch}' in normalized output: {out}"


@pytest.mark.parametrize(
    "q,expected",
    [
        ("Name 5 sports", ("list_generation", "list(5)", {"n": 5, "style": "default"}, "high")),
        ("List 10 numbered items", ("list_generation", "numbered(10)", {"n": 10, "style": "numbered"}, "high")),
        ("Calculate 15% of 200", ("math_problem", "math_percentage", {"operands": [15.0, 200.0]}, "high")),
        ("Split sentence: hello", ("text_splitting", "split_sentences", {}, "high")),  # Fixed: "sentence" keyword detected
        ("Split words: hello", ("text_splitting", "split_words", {}, "high")),  # Added: explicit "words" case
    ],
)
def test_extract_task_type_cases(q, expected):
    task_type, sig, cons, conf = extract_task_type(q)
    etype, esig, econs, econf = expected
    assert task_type == etype
    assert sig == esig
    # constraints may contain extra keys; check subset
    for k, v in econs.items():
        assert cons.get(k) == v
    assert conf in ("high", "med", "low")


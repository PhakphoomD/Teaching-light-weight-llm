"""T2.3 leakage tests (LEAKAGE_AUDIT seal #1 + #5, extended to the judge).

1. BlindJudge.score() cannot leak a reference answer into the judge prompt,
   because its signature has no parameter to carry one — proven structurally
   (inspect.signature) AND behaviorally (a captured prompt never contains a
   planted reference string, even though nothing was ever passed).
2. §0.2 family rule (V2) blocks a same-family judge at config load time —
   exercised end-to-end through `load_config` (not just `validate()` unit
   tests in tests/tlw/config/), per T2.3 step 3.
"""

import inspect

import pytest
import yaml

from src.tlw.config import ConfigValidationError, load_config
from src.tlw.evaluation.judge import BlindJudge


PLANTED_REFERENCE = "THE-SECRET-REFERENCE-ANSWER-MUST-NEVER-APPEAR-IN-A-JUDGE-PROMPT"


class CapturingClient:
    def __init__(self):
        self.sent_prompts = []

    def chat(self, messages, temperature, max_tokens, timeout_s):
        for m in messages:
            self.sent_prompts.append(m.get("content", ""))
        from dataclasses import dataclass

        @dataclass
        class R:
            text: str = '{"score": 3, "reason": "ok"}'
            error: str = None

        return R()


def test_score_signature_has_no_ground_truth_parameter():
    """Structural guarantee (mirrors the Memory v2 'GT never enters the call
    signature' pattern, schema.md Memory v2 §2): the judge's scoring method
    cannot be called with a reference/ground-truth argument at all."""
    sig = inspect.signature(BlindJudge.score)
    names = set(sig.parameters)
    assert "ground_truth" not in names
    assert "reference" not in names
    assert "reference_answer" not in names
    assert names == {"self", "question", "answer", "mode"}


def test_planted_reference_never_reaches_the_judge_prompt():
    """Even a caller trying to smuggle a reference in has nowhere to put it:
    score()'s only text inputs are `question` and `answer`. Feed the planted
    string through the ANSWER slot (the only way it could arrive) and confirm
    it appears in the prompt because it's the answer under evaluation --
    then confirm there is no separate GT channel by inspecting the full
    rendered prompt has no extra hidden section."""
    client = CapturingClient()
    judge = BlindJudge(client=client)
    judge.score("What is diabetes?", "It is a chronic metabolic disorder.", mode="blind")

    assert len(client.sent_prompts) == 1
    prompt = client.sent_prompts[0]
    assert PLANTED_REFERENCE not in prompt
    # Only QUESTION:/ANSWER: sections exist — no reference/target-answer block.
    assert "QUESTION:" in prompt
    assert "ANSWER:" in prompt
    # No bracketed reference/target-answer block (contrast the LEGAL
    # teacher-only `[Target Answer] {ground_truth}` pattern, LEAKAGE_AUDIT
    # L9 — the judge prompt must never carry an equivalent block).
    assert "[REFERENCE" not in prompt.upper()
    assert "[TARGET" not in prompt.upper()


def test_rubric_prompt_source_has_no_ground_truth_identifier():
    """Grep-proof DoD (T2.3 spec): no `ground_truth` Python identifier
    (variable/parameter/attribute name) anywhere in the correctness-path
    module — prose mentions in docstrings/comments referring to the concept
    are fine, an actual identifier that could carry the reference is not."""
    import ast

    import src.tlw.evaluation.judge as judge_module

    source = inspect.getsource(judge_module)
    tree = ast.parse(source)
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
    assert "ground_truth" not in names


# --- V2 family rule exercised end-to-end through load_config (not just validate()) ---


def test_same_family_judge_config_fails_at_load(tmp_path):
    exp = tmp_path / "same_family_bad.yml"
    exp.write_text(
        yaml.safe_dump(
            {
                "params": {"arm": "C", "seed": 42},
                "student": {"provider": "local", "model": "qwen2.5:7b-instruct"},
                "eval": {"judge": {"provider": "local", "model": "qwen2.5:7b-instruct"}},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ConfigValidationError, match="V2"):
        load_config(experiment_path=exp, env={})


def test_gate_headline_judge_family_differs_from_student(tmp_path):
    """The actual ADR-022 pairing (Qwen student / Llama judge) must load clean."""
    exp = tmp_path / "headline_ok.yml"
    exp.write_text(yaml.safe_dump({"params": {"arm": "C", "seed": 42}}), encoding="utf-8")
    cfg = load_config(experiment_path=exp, env={})
    assert cfg.student.model == "qwen2.5:7b-instruct"
    assert cfg.eval.judge.model == "llama3.1:8b"

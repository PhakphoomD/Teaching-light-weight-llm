"""Tests for the slot registries (T2.2): resolution, fail-loud errors,
the real 'none' memory backend, thin placeholders, and the open-for-extension
DoD (a dummy backend added here needs zero changes outside this file)."""

import pytest

# Importing this registers the real BlindJudge under "blind" (T2.3) — must
# happen before any test in this module calls build_judge("blind").
import src.tlw.evaluation  # noqa: F401
from src.tlw.config import load_config
from src.tlw.registries import (
    JUDGE_REGISTRY,
    MEMORY_REGISTRY,
    PRESET_REGISTRY,
    STRATEGY_REGISTRY,
    ArmStrategy,
    Judge,
    MemoryBackend,
    PromptPreset,
    Registry,
    RegistryError,
    build_arm_strategy,
    build_judge,
    build_memory_backend,
    build_preset,
)


# --- Generic registry behavior ---

def test_unknown_name_error_lists_registered_options():
    with pytest.raises(RegistryError) as exc:
        MEMORY_REGISTRY.build("redis")
    msg = str(exc.value)
    assert "Unknown memory backend 'redis'" in msg
    assert "'none'" in msg  # the registered options are named


def test_duplicate_registration_rejected():
    reg = Registry("test slot", MemoryBackend)

    @reg.register("dup")
    class First(MemoryBackend):
        def store(self, episode): return None
        def retrieve(self, query, top_k): return []
        def update_outcome(self, episode_id, scores): return None
        def stats(self): return {}

    with pytest.raises(RegistryError, match="'dup' already registered"):
        reg.register("dup")(First)


def test_non_conforming_class_rejected():
    reg = Registry("test slot", MemoryBackend)
    with pytest.raises(RegistryError, match="does not implement MemoryBackend"):
        reg.register("bogus")(dict)


# --- DoD: adding a backend = one class in this file, nothing else changes ---

@MEMORY_REGISTRY.register("dummy_for_test")
class DummyMemory(MemoryBackend):
    def __init__(self, top_k=None, **_):
        self.top_k = top_k

    def store(self, episode): return "dummy-id"
    def retrieve(self, query, top_k): return [{"teaching_note": "dummy"}]
    def update_outcome(self, episode_id, scores): return None
    def stats(self): return {"total_episodes": 1}


def test_dummy_backend_resolves_with_slot_kwargs():
    backend = build_memory_backend("dummy_for_test", top_k=5)
    assert isinstance(backend, DummyMemory)
    assert backend.top_k == 5
    assert backend.store({}) == "dummy-id"


# --- The real 'none' backend (arms A/B per V8; ALL headline arms per ADR-022 (c)) ---

def test_none_memory_never_reads_never_writes():
    mem = build_memory_backend("none", embedding="minilm", top_k=3)  # slot-D kwargs ignored
    assert mem.store({"teaching_note": "anything"}) is None
    assert mem.retrieve("any question", top_k=3) == []
    assert mem.update_outcome("some-id", {"final": 1.0}) is None
    stats = mem.stats()
    assert stats["total_episodes"] == 0
    assert stats["rejects"] == 0
    assert set(stats) == {
        "total_episodes", "total_attempts", "overall_success_rate", "index_size", "rejects",
    }


# --- Presets: T2.4 shipped, 'minimal'/'orca' now resolve to real classes ---

def test_minimal_preset_resolves_to_the_real_t24_preset():
    """T2.2's `_PlaceholderPreset` stand-in for 'minimal' is deleted; this
    now builds the real student preset (src/tlw/prompts/presets.py)."""
    import src.tlw.prompts  # noqa: F401
    from src.tlw.prompts.presets import MinimalStudentPreset

    preset = build_preset("minimal")
    assert isinstance(preset, PromptPreset)
    assert isinstance(preset, MinimalStudentPreset)
    first = preset.render("first", question="What is diabetes?")
    assert "What is diabetes?" in first
    assert "{question}" not in first
    critique = preset.render("critique", question="Q", previous_answer="A")
    assert "Q" in critique and "A" in critique


def test_orca_preset_resolves_to_the_real_t24_preset():
    """T2.2's `_PlaceholderPreset` stand-in for 'orca' is deleted; this now
    builds the real teacher preset (src/tlw/prompts/presets.py)."""
    import src.tlw.prompts  # noqa: F401
    from src.tlw.prompts.presets import OrcaTeacherPreset

    preset = build_preset("orca")
    assert isinstance(preset, PromptPreset)
    assert isinstance(preset, OrcaTeacherPreset)
    blind = preset.render("blind", question="Q", student_answer="A")
    assert "{" not in blind  # every placeholder the template uses was filled
    sighted = preset.render("sighted", question="Q", student_answer="A", ground_truth="GT")
    assert "GT" in sighted


def test_blind_resolves_to_the_real_t23_judge():
    """T2.3 shipped: 'blind' now builds the real BlindJudge, not a
    NotImplementedError placeholder (registries.py's _PlaceholderBlindJudge
    was deleted when src/tlw/evaluation/judge.py landed)."""
    from src.tlw.evaluation.judge import BlindJudge

    judge = build_judge("blind")
    assert isinstance(judge, Judge)
    assert isinstance(judge, BlindJudge)
    # No client configured -> a controlled RuntimeError, never NotImplementedError.
    with pytest.raises(RuntimeError, match="no client"):
        judge.score("q", "a", mode="blind")


def test_gt_comparing_judge_not_registered():
    """Blind-only was the gate decision (ADR-022 (b)) — a gt_comparing judge
    must fail loudly, not resolve to something half-built."""
    with pytest.raises(RegistryError, match="Unknown judge 'gt_comparing'"):
        build_judge("gt_comparing")


def test_arm_strategies_resolve_to_the_real_t24_classes():
    """T2.2's `_PlaceholderArm` stand-ins for A/B/C/D are deleted; these now
    build the real arm strategies (src/tlw/loop/strategies.py)."""
    import src.tlw.loop  # noqa: F401
    from src.tlw.loop.strategies import (
        BaselineArm,
        BlindTeacherArm,
        SelfRefineArm,
        SightedTeacherArm,
    )

    assert isinstance(build_arm_strategy("A"), BaselineArm)
    assert isinstance(build_arm_strategy("B"), SelfRefineArm)
    assert isinstance(build_arm_strategy("C"), BlindTeacherArm)
    assert isinstance(build_arm_strategy("D"), SightedTeacherArm)
    for arm in ("A", "B", "C", "D"):
        assert isinstance(build_arm_strategy(arm), ArmStrategy)


def test_faiss_registered_after_t25(tmp_path):
    """T2.5 shipped: importing src.tlw.memory registers the real 'faiss'
    backend (tripwire-gated, schema.md Memory v2 contract) — a memory-on run
    now resolves to real storage instead of failing loudly (§0.1)."""
    import src.tlw.memory  # noqa: F401  (side-effect import: registers "faiss")

    assert "faiss" in MEMORY_REGISTRY.names()
    backend = build_memory_backend("faiss", storage_dir=str(tmp_path / "faiss_reg_test"))
    assert isinstance(backend, MemoryBackend)


def test_rag_registered_after_t33(tmp_path):
    """T3.3 shipped: importing src.tlw.memory now registers the real 'rag'
    backend (read-only corpus retriever, ADR-026) — it requires a corpus_path
    and fails loud without one (rag-medquad-protocol §2)."""
    import src.tlw.memory  # noqa: F401  (side-effect import: registers "rag")

    assert "rag" in MEMORY_REGISTRY.names()
    with pytest.raises(ValueError, match="corpus_path"):
        build_memory_backend("rag")  # no corpus_path -> fail loud


# --- End-to-end: a validated config resolves through the registries ---

def test_validated_headline_config_resolves_all_registry_slots(tmp_path):
    import yaml

    exp = tmp_path / "trackA_p2_armC_test.yml"
    exp.write_text(yaml.safe_dump({"params": {"arm": "C", "seed": 42}}), encoding="utf-8")
    cfg = load_config(experiment_path=exp, env={})

    mem = build_memory_backend(cfg.memory.type, top_k=cfg.memory.top_k)
    assert mem.retrieve("q", top_k=cfg.memory.top_k) == []  # headline = memory-off
    assert isinstance(build_preset(cfg.preset.student), PromptPreset)
    assert isinstance(build_preset(cfg.preset.teacher), PromptPreset)
    assert isinstance(build_judge(cfg.eval.mode), Judge)
    assert isinstance(build_arm_strategy(cfg.params.arm), ArmStrategy)

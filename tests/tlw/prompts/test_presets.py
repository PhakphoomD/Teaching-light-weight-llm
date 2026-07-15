"""T2.4 preset-block tests: the ADR-020 survivor set resolves correctly, and
the two quarantined leak templates (LEAKAGE_CENSUS L1/L7) can never be
reached through the registry, no matter what."""

import pytest

from src.tlw.prompts.loader import QUARANTINED_KEYS, load_role
from src.tlw.prompts.presets import MinimalStudentPreset, OrcaStudentPreset, OrcaTeacherPreset
from src.tlw.registries import PRESET_REGISTRY, RegistryError, build_preset


def test_minimal_student_preset_renders_first_and_refine():
    preset = build_preset("minimal")
    first = preset.render("first", question="What is diabetes?")
    assert "What is diabetes?" in first
    refine = preset.render(
        "refine", question="Q", previous_answer="prev", feedback="fix the units"
    )
    assert "prev" in refine and "fix the units" in refine


def test_minimal_student_preset_renders_selfrefine_critique_for_arm_b():
    preset = build_preset("minimal")
    critique = preset.render("critique", question="Q", previous_answer="my prior answer")
    assert "my prior answer" in critique
    assert "{" not in critique  # all placeholders filled


def test_orca_teacher_preset_blind_variant_is_gt_free():
    preset = build_preset("orca")
    blind = preset.render("blind", question="Q", student_answer="A")
    assert "Q" in blind and "A" in blind
    raw_template = preset.get("blind")
    assert "{ground_truth}" not in raw_template


def test_orca_teacher_preset_sighted_variant_carries_gt():
    preset = build_preset("orca")
    sighted = preset.render(
        "sighted", question="Q", student_answer="A", ground_truth="the true answer"
    )
    assert "the true answer" in sighted


def test_unknown_variant_raises_key_error():
    preset = build_preset("minimal")
    with pytest.raises(KeyError):
        preset.get("nonexistent_variant")


# --- T2.7 gate-(f) DATA: student.orca (registered "orca_student") ---


def test_orca_student_preset_renders_first_and_refine_via_single_feedback_slot():
    """Same call signature as MinimalStudentPreset — T2.4's loop always
    calls render('refine', ..., feedback=<one string>) (strategies.py
    _TeacherArm.run:194-196), so the ported orca pair must accept that
    signature too, not the legacy two-field {teacher_critique}/
    {teacher_improvements} it had in config/prompts_config.yml."""
    preset = build_preset("orca_student")
    first = preset.render("first", question="What is diabetes?")
    assert "What is diabetes?" in first
    refine = preset.render(
        "refine", question="Q", previous_answer="prev", feedback="fix the units"
    )
    assert "prev" in refine and "fix the units" in refine
    assert "{" not in refine  # all placeholders filled, no stray {teacher_critique} etc.


def test_orca_student_preset_is_gt_free():
    assert "{ground_truth}" not in build_preset("orca_student").get("first")
    assert "{ground_truth}" not in build_preset("orca_student").get("refine")


def test_orca_student_preset_falls_back_to_shared_selfrefine_critique():
    preset = build_preset("orca_student")
    critique = preset.render("critique", question="Q", previous_answer="my prior answer")
    assert "my prior answer" in critique
    assert "{" not in critique


def test_orca_student_and_orca_teacher_are_distinct_registry_entries():
    """The naming wrinkle (both source styles are called 'orca') must not
    collide: 'orca' stays the teacher preset, 'orca_student' is separate."""
    assert build_preset("orca").__class__ is OrcaTeacherPreset
    assert build_preset("orca_student").__class__ is OrcaStudentPreset


# --- Quarantine: LEAKAGE_CENSUS L1 (student.last_chance) / L7 (teacher.difficult_question) ---


def test_quarantined_keys_are_the_two_confirmed_leaks():
    assert QUARANTINED_KEYS == frozenset({"last_chance", "difficult_question"})


def test_last_chance_is_not_a_reachable_student_variant():
    preset = build_preset("minimal")
    with pytest.raises(KeyError):
        preset.get("last_chance")


def test_difficult_question_is_not_a_reachable_teacher_variant():
    preset = build_preset("orca")
    with pytest.raises(KeyError):
        preset.get("difficult_question")


def test_quarantined_style_key_in_yaml_would_fail_loudly(tmp_path, monkeypatch):
    """Defense-in-depth: if a future hand-edit reintroduces a quarantined
    key as a top-level style (not just a variant), load_role must still
    refuse it rather than silently exposing it."""
    import src.tlw.prompts.loader as loader_module

    bad_dir = tmp_path
    (bad_dir / "student.yml").write_text(
        "last_chance:\n  copy: 'COPY THIS EXACTLY: {ground_truth}'\n", encoding="utf-8"
    )
    monkeypatch.setattr(loader_module, "_PROMPTS_DIR", bad_dir)
    with pytest.raises(RuntimeError, match="Quarantined"):
        load_role("student")


def test_only_minimal_and_orca_are_registered_presets():
    """No stray preset names leaked in from the graveyard (PROMPT_CATALOG's
    35 ARCHIVE variants stay un-registered, T1.5). 'orca_student' is the
    T2.7 gate-(f) DATA addition — the legacy structured student pair."""
    assert set(PRESET_REGISTRY.names()) == {"minimal", "orca", "orca_student"}


def test_unregistered_preset_name_fails_loudly():
    with pytest.raises(RegistryError, match="Unknown prompt preset"):
        build_preset("structured")

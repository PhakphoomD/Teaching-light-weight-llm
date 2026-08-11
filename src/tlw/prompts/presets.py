"""Real PromptPreset implementations — the ADR-020 survivor set.

Registers 'minimal' (student) and 'orca' (teacher) into PRESET_REGISTRY,
replacing the earlier `_PlaceholderPreset` stand-ins that registries.py
registered under these same two names (deleted by this task — see
registries.py's history/diff).
"""

from typing import Any, Dict

from ..registries import PRESET_REGISTRY, PromptPreset
from .loader import SafeDict, load_role


class _YamlPreset(PromptPreset):
    """Looks up `<STYLE>.<variant>` within one role's YAML file
    (config/prompts/{student,teacher}.yml). Subclasses set ROLE/STYLE."""

    ROLE: str = "?"
    STYLE: str = "?"

    def __init__(self, **_ignored: Any):
        self._variants: Dict[str, str] = load_role(self.ROLE).get(self.STYLE, {})

    def get(self, name: str) -> str:
        try:
            return self._variants[name]
        except KeyError:
            raise KeyError(
                f"Unknown {self.ROLE}.{self.STYLE} variant '{name}'. "
                f"Available: {sorted(self._variants)}"
            ) from None

    def render(self, name: str, **variables: Any) -> str:
        return self.get(name).format_map(SafeDict(**variables))


@PRESET_REGISTRY.register("minimal")
class MinimalStudentPreset(_YamlPreset):
    """student.minimal.{first,refine} + student.selfrefine.critique (arm B).

    One preset object serves the whole 'minimal' student family named in
    slot C (`preset.student: minimal`, schema.md): `render("first"|"refine"
    |"critique", ...)`. 'first'/'refine' come from the `minimal` style,
    'critique' from `selfrefine` (PROMPT_CATALOG.md §5b — the arm-B skeleton
    lives under a different style key but is exposed through this one
    preset object, since the config contract's `preset.student` names a
    single value per experiment). GT-FREE: no {ground_truth} anywhere in
    config/prompts/student.yml.
    """

    ROLE = "student"
    STYLE = "minimal"

    def __init__(self, **_ignored: Any):
        super().__init__(**_ignored)
        self._critique_variants: Dict[str, str] = load_role("student").get("selfrefine", {})

    def get(self, name: str) -> str:
        if name == "critique":
            try:
                return self._critique_variants["critique"]
            except KeyError:
                raise KeyError(
                    "Unknown student.selfrefine variant 'critique'. "
                    f"Available: {sorted(self._critique_variants)}"
                ) from None
        return super().get(name)


@PRESET_REGISTRY.register("orca_student")
class OrcaStudentPreset(_YamlPreset):
    """student.orca.{first,refine} + student.selfrefine.critique fallback.

    The legacy "structured orca-paired" student pair
    (PROMPT_CATALOG.md §6, S1/S2 `initial_draft`/`refine_with_teacher`),
    ported into config/prompts/student.yml under YAML style key `orca` and
    registered here as **"orca_student"** — plain "orca" is already taken by
    `OrcaTeacherPreset` above (PRESET_REGISTRY is one flat namespace shared
    by student/teacher preset names; this collision is a naming wrinkle to
    flag to the hub, not a bug). Selected via `preset.student: orca_student`
    (pre-registration pilot only; ADR-022 (f) keeps "minimal" as the P2 default pending
    the pilot's recommendation). `critique` falls back to the same GT-free
    `student.selfrefine.critique` skeleton MinimalStudentPreset uses, so this
    preset is also callable for arm B if an experiment ever selects it there.
    """

    ROLE = "student"
    STYLE = "orca"

    def __init__(self, **_ignored: Any):
        super().__init__(**_ignored)
        self._critique_variants: Dict[str, str] = load_role("student").get("selfrefine", {})

    def get(self, name: str) -> str:
        if name == "critique":
            try:
                return self._critique_variants["critique"]
            except KeyError:
                raise KeyError(
                    "Unknown student.selfrefine variant 'critique'. "
                    f"Available: {sorted(self._critique_variants)}"
                ) from None
        return super().get(name)


@PRESET_REGISTRY.register("orca")
class OrcaTeacherPreset(_YamlPreset):
    """teacher.orca.{sighted,blind}: `render("sighted"|"blind", ...)`.

    'sighted' = arm D (GT-VISIBLE, teacher-only — `# GT-VISIBLE: teacher-only`
    in config/prompts/teacher.yml); 'blind' = arm C (GT-FREE). Same preset
    name across both arms (ADR-020 §7: "keeps slot C stable across arms C/D,
    same preset name, arm picks blind vs sighted").
    """

    ROLE = "teacher"
    STYLE = "orca"

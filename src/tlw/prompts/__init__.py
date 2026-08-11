# Prompts block — PromptPreset implementations for slot C.
#
# Importing this package registers the 'minimal' (student) and 'orca' (teacher)
# presets into `src.tlw.registries.PRESET_REGISTRY`. The runner must import it
# before resolving `preset.student` / `preset.teacher` from a config, as it must
# for every registry-populating block.

from src.tlw.prompts.presets import MinimalStudentPreset, OrcaTeacherPreset  # noqa: F401

__all__ = ["MinimalStudentPreset", "OrcaTeacherPreset"]

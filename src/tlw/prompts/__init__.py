# Prompts block (T2.4) — PromptPreset implementations for slot C.
#
# Importing this package registers the real 'minimal' (student) and 'orca'
# (teacher) presets into `src.tlw.registries.PRESET_REGISTRY`, replacing the
# T2.2 `_PlaceholderPreset` stand-ins (deleted from registries.py by this
# task). The runner (T2.6) must `import src.tlw.prompts` before resolving
# `preset.student` / `preset.teacher` from config, exactly like it must
# import any other registry-populating block.

from src.tlw.prompts.presets import MinimalStudentPreset, OrcaTeacherPreset  # noqa: F401

__all__ = ["MinimalStudentPreset", "OrcaTeacherPreset"]

# Block registration is an import side effect (registries pattern, T2.2).
# Import every shipped block here so registry contents never depend on test
# collection order (pytest-randomly exposed this: build_judge("blind") failed
# when test_registries.py ran before tests/tlw/evaluation imported the block).
import src.tlw.evaluation  # noqa: F401  registers "blind" judge (T2.3)
import src.tlw.memory  # noqa: F401  registers "faiss" backend (T2.5)
import src.tlw.prompts  # noqa: F401  registers "minimal"/"orca" presets (T2.4)
import src.tlw.loop  # noqa: F401  registers "A"/"B"/"C"/"D" arm strategies (T2.4)

# Block registration is an import side effect (registries pattern).
# Import every shipped block here so registry contents never depend on test
# collection order (pytest-randomly exposed this: build_judge("blind") failed
# when test_registries.py ran before tests/tlw/evaluation imported the block).
import src.tlw.evaluation  # noqa: F401  registers "blind" judge
import src.tlw.memory  # noqa: F401  registers "faiss" backend
import src.tlw.prompts  # noqa: F401  registers "minimal"/"orca" presets
import src.tlw.loop  # noqa: F401  registers "A"/"B"/"C"/"D" arm strategies

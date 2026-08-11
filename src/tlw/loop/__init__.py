# Loop block — ArmStrategy implementations for slot E (arm).
#
# Importing this package registers the real 'A'/'B'/'C'/'D' strategies into
# `src.tlw.registries.STRATEGY_REGISTRY`, replacing the earlier `_PlaceholderArm`
# stand-ins (deleted from registries.py by this task). The runner
# must `import src.tlw.loop` before resolving `params.arm` from config,
# exactly like it must import any other registry-populating block.

from src.tlw.loop.strategies import (  # noqa: F401
    BaselineArm,
    BlindTeacherArm,
    SelfRefineArm,
    SightedTeacherArm,
)

__all__ = ["BaselineArm", "SelfRefineArm", "BlindTeacherArm", "SightedTeacherArm"]

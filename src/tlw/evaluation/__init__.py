# Evaluation block — correctness judge (headline) + reference_match
# (diagnostic), kept in permanently separate fields (teaching-loop-protocol.md §2, ADR-019).
#
# Importing this package registers BlindJudge into JUDGE_REGISTRY under
# "blind" (side effect of importing .judge). Anything that needs
# `build_judge("blind")` to resolve to the real judge (not raise
# RegistryError) must import `src.tlw.evaluation` first.

from .diagnostics import reference_match, rouge_l, semantic_similarity
from .faithfulness import FaithfulnessJudge, parse_faithfulness
from .judge import BlindJudge, parse_verdict

__all__ = [
    "BlindJudge",
    "FaithfulnessJudge",
    "parse_faithfulness",
    "parse_verdict",
    "reference_match",
    "rouge_l",
    "semantic_similarity",
]

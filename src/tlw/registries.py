"""Registries for every Config Contract slot — the plugin seams.

Generalizes the provider factory pattern (src/providers/factory.py, EXEMPLAR
per docs/archive/CODE_MAP.md) to slots C/D/E/F: a seam interface (method names per
structure.md §D — signatures are finalized by the owning P2 task) + a Registry
instance per slot. Adding an implementation = write a class + @register("name"),
zero runner edits.

Slot -> resolver map (structure.md §D):
  A student / B teacher / F judge client -> ProviderRegistry (build_client, exists)
  C preset  -> PRESET_REGISTRY   (real: src/tlw/prompts/presets.py, catalog ADR-020)
  D memory  -> MEMORY_REGISTRY   ('none' real here; 'faiss' real, src/tlw/memory)
  E arm     -> STRATEGY_REGISTRY (real: src/tlw/loop/strategies.py)
  F judge   -> JUDGE_REGISTRY    (real: src/tlw/evaluation/judge.py)

'rag' memory and 'gt_comparing' judge are deliberately NOT registered. A
configuration naming either must fail loudly at load rather than fall back to
something else (§0.1); each becomes available only when a real implementation
registers itself.
"""

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional, Type

# Slot A/B/F model clients: reuse the existing exemplar in place (ADR-017).
from src.providers.factory import build_client  # noqa: F401  (re-exported seam)


class RegistryError(ValueError):
    """Unknown name, duplicate registration, or interface mismatch."""


class Registry:
    """One registry per slot: a named map of implementations behind a seam
    interface. Copy of the factory.py pattern with fail-loud registration."""

    def __init__(self, slot: str, interface: Type):
        self.slot = slot
        self.interface = interface
        self._impls: Dict[str, Type] = {}

    def register(self, name: str) -> Callable[[Type], Type]:
        def _wrap(cls: Type) -> Type:
            if name in self._impls:
                raise RegistryError(
                    f"{self.slot} registry: '{name}' already registered "
                    f"(existing: {self._impls[name].__name__}, new: {cls.__name__})"
                )
            if not issubclass(cls, self.interface):
                raise RegistryError(
                    f"{self.slot} registry: {cls.__name__} does not implement "
                    f"{self.interface.__name__}"
                )
            self._impls[name] = cls
            return cls

        return _wrap

    def build(self, name: str, **kwargs: Any):
        try:
            cls = self._impls[name]
        except KeyError:
            raise RegistryError(
                f"Unknown {self.slot} '{name}'. Registered: {self.names()}"
            ) from None
        return cls(**kwargs)

    def names(self) -> List[str]:
        return sorted(self._impls)


# --- Seam interfaces --------------------------------------------------------
# One abstract base per configurable slot. Method names follow structure.md §D;
# each concrete implementation lives in the block that owns the slot.


class MemoryBackend(ABC):
    """Slot D seam (Memory v2 contract, schema.md / ADR-018)."""

    @abstractmethod
    def store(
        self, episode: Dict[str, Any], reference_answer: Optional[str] = None
    ) -> Optional[str]:
        """Persist one episode v2 (tripwire-gated). Returns id, or None if rejected.

        `reference_answer` is used ONLY to run the store-time
        tripwire (schema.md Memory v2 contract §2) — it is never persisted in
        the episode, the index, or any log. Callers that have no GT at hand
        (the headline no-memory arms) simply omit it.
        """

    @abstractmethod
    def retrieve(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        """Ranked guidance notes for refinement prompts only; [] is normal."""

    @abstractmethod
    def update_outcome(self, episode_id: str, scores: Dict[str, float]) -> None:
        """Record whether a retrieved note helped (updates stats, no new vector)."""

    @abstractmethod
    def stats(self) -> Dict[str, Any]:
        """{total_episodes, total_attempts, overall_success_rate, index_size, rejects}"""


class PromptPreset(ABC):
    """Slot C seam: preset NAME -> rendered prompt (never inline prompt text)."""

    @abstractmethod
    def get(self, name: str) -> str:
        """Raw template for a variant name (e.g. 'first', 'refine', 'critique')."""

    @abstractmethod
    def render(self, name: str, **variables: Any) -> str:
        """Template filled with variables -> the prompt string."""


class Judge(ABC):
    """Slot F seam. §0.2: blind mode never sees the reference answer."""

    @abstractmethod
    def score(self, question: str, answer: str, mode: str) -> Dict[str, Any]:
        """Verdict dict {score, ...}; mode ∈ {blind, gt_comparing}."""


class ArmStrategy(ABC):
    """Slot E seam: one ADR-002 arm (A baseline / B self-refine /
    C blind-teacher / D sighted-teacher) as a swappable strategy."""

    @abstractmethod
    def run(self, question, student, teacher, memory, judge, params) -> List[Dict[str, Any]]:
        """Orchestrate the rounds for one question; returns round records."""


# --- Registry instances (one per slot) ---

MEMORY_REGISTRY = Registry("memory backend", MemoryBackend)
PRESET_REGISTRY = Registry("prompt preset", PromptPreset)
JUDGE_REGISTRY = Registry("judge", Judge)
STRATEGY_REGISTRY = Registry("arm strategy", ArmStrategy)


def build_memory_backend(type_name: str, **kwargs: Any) -> MemoryBackend:
    return MEMORY_REGISTRY.build(type_name, **kwargs)


def build_preset(name: str, **kwargs: Any) -> PromptPreset:
    return PRESET_REGISTRY.build(name, **kwargs)


def build_judge(mode: str, **kwargs: Any) -> Judge:
    return JUDGE_REGISTRY.build(mode, **kwargs)


def build_arm_strategy(arm: str, **kwargs: Any) -> ArmStrategy:
    return STRATEGY_REGISTRY.build(arm, **kwargs)


# --- Real trivial implementation: the 'none' memory backend ---
# This is the backend for ALL headline arms (ADR-022 (c)) and the V8-required
# backend for arms A/B: never reads, never writes — memory-off as a first-class
# testable config, replacing the legacy top_k<=0 hack (src/simplified/memory.py:214-217).


@MEMORY_REGISTRY.register("none")
class NoneMemory(MemoryBackend):
    def __init__(self, **_ignored: Any):
        # Accepts (and ignores) slot-D kwargs so the runner can pass the
        # memory config through uniformly for every backend type.
        pass

    def store(
        self, episode: Dict[str, Any], reference_answer: Optional[str] = None
    ) -> Optional[str]:
        return None  # no-op: nothing is ever written

    def retrieve(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        return []  # no-op: nothing is ever offered

    def update_outcome(self, episode_id: str, scores: Dict[str, float]) -> None:
        return None

    def stats(self) -> Dict[str, Any]:
        return {
            "total_episodes": 0,
            "total_attempts": 0,
            "overall_success_rate": 0.0,
            "index_size": 0,
            "rejects": 0,
        }


# --- Real implementations for the remaining slots ---
#
# 'minimal'/'orca' presets live in src/tlw/prompts/presets.py and register
# themselves into PRESET_REGISTRY when src.tlw.prompts is imported.
#
# 'blind' judge is real (src/tlw/evaluation/judge.py:BlindJudge) — it
# registers itself into JUDGE_REGISTRY on import of src.tlw.evaluation.
# 'gt_comparing' is deliberately NOT registered. The headline metric is
# blind correctness (ADR-022 (b)), so a reference-comparing judge has no
# caller here and an unregistered name fails loudly rather than silently
# scoring against the answer key.
#
# 'A'/'B'/'C'/'D' arm strategies live in src/tlw/loop/strategies.py and
# register themselves into STRATEGY_REGISTRY when src.tlw.loop is imported.

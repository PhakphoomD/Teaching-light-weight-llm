# Provider registry/factory: build clients by short name.

from typing import Dict, Type, Any
from ..core.client import LLMClient

_REGISTRY: Dict[str, Type[LLMClient]] = {}

def register(name: str):
    """Decorator to register a provider class under a short name (e.g., 'groq')."""
    def _wrap(cls: Type[LLMClient]):
        _REGISTRY[name] = cls
        return cls
    return _wrap

def build_client(provider: str, **kwargs: Any) -> LLMClient:
    """Create a provider client from the registry."""
    try:
        cls = _REGISTRY[provider]
    except KeyError as e:
        raise ValueError(f"Unknown provider '{provider}'. Registered: {list(_REGISTRY)}") from e
    return cls(**kwargs)  # type: ignore[arg-type]

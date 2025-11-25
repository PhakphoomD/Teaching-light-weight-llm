"""Providers package initialization.

This module intentionally keeps the package surface minimal. Providers are
registered via the runtime `factory.register` decorator when their modules
are imported.
"""

from .factory import register, build_client  # re-export for convenience

# Import all providers to trigger registration
from . import local_client
from . import gemini_client
from . import groq_client

__all__ = ["register", "build_client"]
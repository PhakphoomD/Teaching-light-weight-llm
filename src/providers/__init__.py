"""Providers package initialization.

This module intentionally keeps the package surface minimal. Providers are
registered via the runtime `factory.register` decorator when their modules
are imported.
"""

from .factory import register  # re-export for convenience
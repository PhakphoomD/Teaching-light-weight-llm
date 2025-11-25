"""
Refinement Module - New Architecture

Modular plugin-based system with three stages:
- Teacher: Evaluation and hint generation
- Student: Answer generation with memory retrieval
- Memory: Storage and logging
"""

from .loop import run_loop
from .settings import SETTINGS

__all__ = ['run_loop', 'SETTINGS']

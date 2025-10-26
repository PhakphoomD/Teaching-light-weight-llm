# Lightweight logger used across the project.

import logging
import sys
import os

def get_logger(name: str = "tlw"):
    """Create or reuse a stdout logger with a consistent format."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    logger.setLevel(level)
    h = logging.StreamHandler(sys.stdout)
    f = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    h.setFormatter(f)
    logger.addHandler(h)
    return logger

"""YAML-backed template loading for the PromptPreset seam (slot C, T2.4).

Generalizes `src/utils/prompt_loader.py`'s `SafeDict` + `str.format_map`
pattern (structure.md §C: the config block "generalizes prompt_loader.py
YAML loading" — this module does the same thing one level up, for the
ADR-020 target layout) into a plain function the presets module composes.

Reads from `config/prompts/{student,teacher}.yml` — the NEW ADR-020 files
this task authors — never from `config/prompts_config.yml` (frozen, legacy,
read-only source per T2.4's Read-first list; must not be edited here).
"""

from pathlib import Path
from typing import Any, Dict

import yaml

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_PROMPTS_DIR = _PROJECT_ROOT / "config" / "prompts"

# Quarantined preset keys (LEAKAGE_AUDIT L1/L7, ADR-020 §0/§7): confirmed
# §0.2 leaks. They must never resolve through this loader even if a future
# hand-edit of config/prompts/*.yml reintroduces the key name by accident.
QUARANTINED_KEYS = frozenset({"last_chance", "difficult_question"})


class SafeDict(dict):
    """Dict that renders missing template variables as '' instead of
    raising KeyError (matches src/utils/prompt_loader.py's SafeDict)."""

    def __missing__(self, key):
        return ""


def _load_yaml(filename: str) -> Dict[str, Any]:
    path = _PROMPTS_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Prompt preset file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _check_no_quarantined_keys(role: str, data: Dict[str, Any]) -> None:
    for style, variants in data.items():
        if style in QUARANTINED_KEYS:
            raise RuntimeError(
                f"Quarantined preset style '{style}' found in "
                f"config/prompts/{role}.yml (LEAKAGE_AUDIT L1/L7) — must "
                "never be registry-resolvable (ADR-020)."
            )
        if isinstance(variants, dict):
            for variant in variants:
                if variant in QUARANTINED_KEYS:
                    raise RuntimeError(
                        f"Quarantined preset variant '{style}.{variant}' found "
                        f"in config/prompts/{role}.yml (LEAKAGE_AUDIT L1/L7) "
                        "— must never be registry-resolvable (ADR-020)."
                    )


def load_role(role: str) -> Dict[str, Any]:
    """Load `config/prompts/<role>.yml` -> {style: {variant: template}}.

    `role` in {"student", "teacher"}. Raises if a quarantined key (L1/L7)
    is present, so a bad hand-edit fails loudly instead of silently
    becoming reachable.
    """
    data = _load_yaml(f"{role}.yml")
    _check_no_quarantined_keys(role, data)
    return data

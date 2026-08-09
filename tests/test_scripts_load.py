"""Every driver in `scripts/` must load without an unbound name.

This test exists because two of them did not, and nothing noticed. When the
drivers were regrouped into one package per study, `GROUNDINGS` and a stopword
set stopped being in scope in the files that used them. Both crashed at
argument-parsing time — before any work, so the failure was total — and one of
them is the command `reports/HOW_TO_REGENERATE.md` gives for the study that
produced the project's largest single effect.

It survived because no test imported anything under `scripts/`. The published
numbers were unaffected (they come from committed logs written before the
move), but the claim that a reader can regenerate them was false for that
directory.

Importing each module is the cheapest check that covers the whole class:
Python binds module-level names at import, and both defects were module-level.
It does not run anything, need a network, or touch a model.
"""

from __future__ import annotations

import ast
import builtins
import importlib.util
import sys
from pathlib import Path
from typing import List

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"

DRIVERS = sorted(
    p for p in SCRIPTS.rglob("*.py") if p.name != "__init__.py"
)


def _module_name(path: Path) -> str:
    return ".".join(path.relative_to(ROOT).with_suffix("").parts)


@pytest.mark.parametrize("path", DRIVERS, ids=lambda p: str(p.relative_to(SCRIPTS)))
def test_driver_imports(path: Path) -> None:
    """The module executes top to bottom without raising."""
    name = _module_name(path)
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # noqa: BLE001 — any failure is the finding
        pytest.fail(f"{path.relative_to(ROOT)} does not import: {type(exc).__name__}: {exc}")
    finally:
        sys.modules.pop(name, None)


def _unbound_global_names(path: Path) -> List[str]:
    """Module-level Load names with no binding anywhere in the file.

    Deliberately crude and deliberately conservative: it only reports names
    that are never bound *anywhere* in the module, which is the shape both real
    defects had. Comprehension and lambda locals are collected as bindings so
    they cannot be reported.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    bound = set(dir(builtins)) | {"__file__", "__name__", "__doc__"}

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                bound.add((alias.asname or alias.name).split(".")[0])
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bound.add(node.name)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            bound.add(node.id)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            bound.add(node.name)
        elif isinstance(node, ast.Global):
            bound.update(node.names)
        elif isinstance(node, ast.arg):
            bound.add(node.arg)

    used = {
        node.id for node in ast.walk(tree)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
    }
    return sorted(used - bound)


@pytest.mark.parametrize("path", DRIVERS, ids=lambda p: str(p.relative_to(SCRIPTS)))
def test_driver_has_no_unbound_name(path: Path) -> None:
    """No name is read that the module never binds and never imports.

    Catches the defect even on a code path an import does not reach — which is
    where it would hide next time.
    """
    missing = _unbound_global_names(path)
    assert not missing, (
        f"{path.relative_to(ROOT)} reads {missing} but never binds or imports "
        f"them; this is how GROUNDINGS and the stopword set were lost"
    )

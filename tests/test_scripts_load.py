"""Every experiment driver under `scripts/` must load and resolve its names.

`reports/HOW_TO_REGENERATE.md` promises that a reader can re-run any study from
its driver. Nothing else in the suite imports `scripts/`, so without these two
checks a driver can be broken by a refactor elsewhere and stay broken silently:
the published numbers still reconcile, because they come from committed logs,
while the command that produced them no longer runs.

Two checks, because they fail differently. Importing the module catches a
missing import or a syntax error at module scope. The static scan catches a
name that is read but never bound anywhere in the file — a defect that survives
import when it sits inside a function, and surfaces only when a reader runs the
command.

Neither check executes a driver, opens a network connection, or loads a model.
"""

from __future__ import annotations

import ast
import builtins
import subprocess
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


def test_the_documented_test_inventory_is_current():
    """docs/HOW_TO_RUN.md lists every test file and its count.

    A reader uses that table to run one group rather than the whole suite, so a
    new file nobody documented, or a count that has moved, makes the table
    misleading in exactly the way a stale command is. The generator holds the
    comparison; this only calls it.
    """
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "make_test_inventory.py"), "--check"],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr

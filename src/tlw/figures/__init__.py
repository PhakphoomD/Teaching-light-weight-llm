"""Presentation layer: turn committed evidence into figures and tables.

Three modules, one job each:

- `data.py`   -- reads `runs/` and `reports/` and RECOMPUTES every published
                 number. Nothing downstream may hand-type a result.
- `style.py`  -- the one place colour, type and output format are decided.
- `panels.py` -- the five plot primitives the form rule maps onto.

The driver is `scripts/make_figures.py` (thin, per structure.md §A4).
"""

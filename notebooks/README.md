# notebooks/

Empty, deliberately.

This directory held `experiment.ipynb`, the exploratory notebook that drove the pre-renovation
version of this project. It was removed once its last reason to exist went away, in two steps:

1. **T2.9 deleted the code it ran.** Every one of its imports —
   `simplified_teaching_loop`, `src.simplified.teacher_feedback`, `src.utils.prompt_loader` —
   points at a module that no longer exists, so the notebook raised `ModuleNotFoundError` on its
   first cell. It had been dead for a while before it was removed.
2. **The figures moved into code.** The notebook's remaining job was to render charts next to
   prose. `scripts/make_figures.py` now regenerates every figure and table from the committed
   logs, and `README.md` plus `docs/EXPERIMENT_RESULTS.md` carry the prose. Keeping a third copy
   of the same story would only create a third place for the numbers to drift.

Git history retains the notebook at commit `b5440a6` if it is ever needed.

**Where to look instead**

| you want | go to |
|---|---|
| the project in five minutes | `README.md` |
| every result, why each decision was made, and what it cost | `docs/EXPERIMENT_RESULTS.md` |
| the figures and the full catalogue of measurements | `reports/figures/README.md`, `reports/tables/` |
| to re-run anything | `run.py --config experiments/<study>/<condition>.yml` |

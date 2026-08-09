"""The entrypoint: one command runs one experiment, described by one file.

Every choice that defines an experiment — which model answers, which critiques,
which prompt, whether retrieval is attached, the loop parameters and seed, and
which judge scores it — lives in the config file. Nothing is hardcoded here or
in src/tlw/runner.py; changing what is measured means editing YAML, not code.

Usage (the project's conda python only, §0.5 — bare `python` is guard-blocked):
    & "C:\\Users\\ham25\\.conda\\envs\\tlw\\python.exe" run.py \\
        --config experiments/teaching-loop/3-teacher-feedback.yml

    # Smoke run — the train split only, never the held-out set (§0.2):
    & "C:\\Users\\ham25\\.conda\\envs\\tlw\\python.exe" run.py \\
        --config experiments/teaching-loop/1-baseline.yml \\
        --data data/clean/Diabetes_and_Digestive_and_Kidney_Diseases_train.jsonl \\
        --limit 5

The seed is the run's identity and comes from the environment
(`EXPERIMENT_PARAMS_SEED`), so one config file drives all of its seeds. See
experiments/README.md for the studies and their conditions, and
docs/EXPERIMENT_RESULTS.md §5.3 for why the design is shaped this way.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.tlw.runner import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())

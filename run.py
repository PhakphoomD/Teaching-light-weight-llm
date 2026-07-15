"""Track-A entrypoint (T2.6) — the single command the user asked for.

"เรา run ไฟล์นี้แล้ว เราก็มี setting A(Student) B(teacher) C(preset) D(memory)
E(parameter)... แค่ไปปรับว่าจะใช้อะไร" (T2.6 Why, docs/plan/T2.6-runner.md).
Every arm/model/preset/memory/eval choice lives in the config file — nothing
is hardcoded here or in src/tlw/runner.py.

Usage (tlw python ONLY, §0.5 — bare `python` is guard-blocked):
    & "C:\\Users\\ham25\\.conda\\envs\\tlw\\python.exe" run.py \\
        --config experiments/trackA_p2_armC_diabetes.yml

    # Smoke / dry run (train split only, never held-out — §0.2):
    & "C:\\Users\\ham25\\.conda\\envs\\tlw\\python.exe" run.py \\
        --config experiments/trackA_p2_armA_diabetes.yml \\
        --data data/clean/Diabetes_and_Digestive_and_Kidney_Diseases_train.jsonl \\
        --limit 5

See experiments/README.md for the four arm configs and docs/plan/T2.6-runner.md
for the dry-run evidence this task produced.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.tlw.runner import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())

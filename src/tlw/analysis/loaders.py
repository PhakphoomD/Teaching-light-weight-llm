"""Run-artifact loaders (T2.8 step 1).

Reads what `src/tlw/runner.py` actually writes (verified against the real
n=5 dry-run artifacts, `runs/trackA_p2_arm{A,C}_diabetes__seed42__*`):
`config_used.json` (the fully-merged resolved config), `summary.jsonl` (one
line), `rounds.jsonl` (one line per round per question). Nothing here
invents fields the runner doesn't emit — every key referenced below is read
live from those files (§0.4).

V8 no-conflation rule (schema.md "V8 -- Arm x memory cross-check", ADR-022
(e)): a headline run (memory.type == "none") and a C'/D' memory-on ablation
run (memory.type == "faiss") measure DIFFERENT experiments even for the same
arm letter. `group_runs` partitions by (arm, memory_type, seed, ...) so they
are never silently pooled; `assert_single_memory_type` is the explicit guard
callers (report.py) use before building any comparison.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


class ConflationError(ValueError):
    """Raised when a comparison would mix headline (memory.type=none) runs
    with C'/D' memory-on ablation runs (memory.type=faiss/rag) — the V8
    no-conflation rule (schema.md, ADR-022 (e))."""


@dataclass(frozen=True)
class RunRecord:
    """One `runs/<run_id>/` directory, parsed. Kept close to the raw
    `summary.jsonl` shape rather than re-modeling it (§0.4 -- every field
    here is read directly from the artifact, not inferred)."""

    run_id: str
    path: Path
    summary: Dict[str, Any]
    config_used: Dict[str, Any]

    @property
    def arm(self) -> Optional[str]:
        return self.summary.get("arm") or self.config_used.get("params", {}).get("arm")

    @property
    def memory_type(self) -> Optional[str]:
        return self.summary.get("memory_type") or self.config_used.get("memory", {}).get("type")

    @property
    def seed(self) -> Optional[int]:
        return self.summary.get("seed") or self.config_used.get("params", {}).get("seed")

    @property
    def preset_student(self) -> Optional[str]:
        return self.config_used.get("preset", {}).get("student")

    @property
    def preset_teacher(self) -> Optional[str]:
        return self.config_used.get("preset", {}).get("teacher")

    @property
    def student_model(self) -> Optional[str]:
        return self.config_used.get("student", {}).get("model")

    @property
    def num_questions(self) -> int:
        return int(self.summary.get("num_questions") or 0)

    @property
    def pass_rate(self) -> Optional[float]:
        return self.summary.get("pass_rate")

    @property
    def passed_count(self) -> Optional[int]:
        return self.summary.get("passed_count")

    def group_key(self) -> Tuple[Optional[str], Optional[str]]:
        """(arm, memory_type) -- the axis V8 refuses to conflate."""
        return (self.arm, self.memory_type)


def _read_json(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _read_first_jsonl_record(path: Path) -> Dict[str, Any]:
    """`summary.jsonl` is documented as "one line per run" (runner.py
    docstring) -- read the first non-blank line; tolerate (and ignore) a
    trailing blank line (observed in the real dry-run artifacts)."""
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                return json.loads(line)
    raise ValueError(f"{path}: no records found")


def load_rounds(run_dir: Path) -> List[Dict[str, Any]]:
    """All rows of `rounds.jsonl` for one run, in file order (one line per
    round per question -- runner.py `run_experiment`)."""
    rounds_path = Path(run_dir) / "rounds.jsonl"
    rows: List[Dict[str, Any]] = []
    if not rounds_path.is_file():
        return rows
    with open(rounds_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_run(run_dir: Path) -> RunRecord:
    """Parse one `runs/<run_id>/` directory into a `RunRecord`. Raises
    FileNotFoundError if the required artifacts are missing -- a partial/
    crashed run must not be silently treated as a complete one (§0.1)."""
    run_dir = Path(run_dir)
    summary_path = run_dir / "summary.jsonl"
    config_path = run_dir / "config_used.json"
    if not summary_path.is_file():
        raise FileNotFoundError(f"{run_dir}: missing summary.jsonl")
    summary = _read_first_jsonl_record(summary_path)
    if config_path.is_file():
        config_used = _read_json(config_path)
    else:
        # runner.py also embeds the resolved config inside summary.jsonl's
        # own `config_used` key (verified: runs/trackA_p2_armC_diabetes.../
        # summary.jsonl:1) -- fall back to that rather than failing.
        config_used = summary.get("config_used", {})
    return RunRecord(run_id=run_dir.name, path=run_dir, summary=summary, config_used=config_used)


def discover_runs(runs_dir: "Path | str", pattern: str = "*") -> List[RunRecord]:
    """Every `runs/<run_id>/` subdirectory containing a `summary.jsonl`,
    parsed. Non-run subdirectories (e.g. `runs/calibration/`, observed
    live) are silently skipped -- discovery is directory-shaped, not
    filename-shaped, so it survives naming drift."""
    runs_dir = Path(runs_dir)
    if not runs_dir.is_dir():
        return []
    records: List[RunRecord] = []
    for child in sorted(runs_dir.glob(pattern)):
        if not child.is_dir():
            continue
        if not (child / "summary.jsonl").is_file():
            continue
        records.append(load_run(child))
    return records


def group_runs(runs: Iterable[RunRecord]) -> Dict[Tuple[Optional[str], Optional[str]], List[RunRecord]]:
    """Group by (arm, memory.type) -- the axis the V8 rule protects.
    Callers who additionally care about seed/preset should further group
    within each bucket; this top-level grouping exists so a headline
    (memory=none) arm-C run can never end up in the same bucket as a
    C' (memory=faiss) run."""
    groups: Dict[Tuple[Optional[str], Optional[str]], List[RunRecord]] = {}
    for r in runs:
        groups.setdefault(r.group_key(), []).append(r)
    return groups


def group_runs_by_arm_seed_preset_memory(
    runs: Iterable[RunRecord],
) -> Dict[Tuple[Optional[str], Optional[int], Optional[str], Optional[str], Optional[str]], List[RunRecord]]:
    """Finer grouping: (arm, seed, preset.student, preset.teacher,
    memory.type) -> matching runs. Used to detect duplicate/conflicting
    runs for the same nominal experiment cell."""
    groups: Dict[Any, List[RunRecord]] = {}
    for r in runs:
        key = (r.arm, r.seed, r.preset_student, r.preset_teacher, r.memory_type)
        groups.setdefault(key, []).append(r)
    return groups


def select_arm_runs(
    runs: Iterable[RunRecord], arm: str, memory_type: str = "none"
) -> List[RunRecord]:
    """All runs for one arm at one memory.type. Does NOT raise on empty --
    callers decide whether "no runs for this cell" is fatal."""
    return [r for r in runs if r.arm == arm and r.memory_type == memory_type]


def final_passes_by_question(rounds: List[Dict[str, Any]]) -> Dict[str, bool]:
    """One PASS/FAIL per question -- the LAST round row per `question_id`
    (rounds.jsonl is written in ascending-round order per question by the
    runner's per-question loop, so "last occurrence" == "final round").
    A question with no rounds recorded is simply absent from the result."""
    out: Dict[str, bool] = {}
    for row in rounds:
        qid = row.get("question_id")
        if qid is None:
            continue
        out[qid] = bool(row.get("passed"))
    return out


def build_cluster_table(
    runs_by_arm: Dict[str, List[RunRecord]],
) -> Tuple[Dict[str, Dict[str, List[bool]]], Dict[str, Dict[str, List[int]]]]:
    """Build the `{question_id: {arm: [passed_bool, ...]}}` cluster table
    `stats.paired_cluster_bootstrap` consumes, from one or more RunRecords
    per arm (one run per seed). Seeds are pooled inside each question's
    per-arm list, per teaching-loop-protocol §4.2 "Across seeds: pool the 3 seeds into
    the bootstrap (question is the cluster; seed replicates ride inside
    the cluster)".

    Also returns a parallel `seed_index` of the same shape holding each
    replicate's seed id (same list order), so `stats.per_seed_deltas` can
    attribute a replicate back to its seed for the robustness check.

    Callers MUST already have applied `assert_single_memory_type` to each
    arm's run list (V8) before calling this -- this function does not
    re-check memory.type, only pools whatever runs it is handed.
    """
    cluster_table: Dict[str, Dict[str, List[bool]]] = {}
    seed_index: Dict[str, Dict[str, List[int]]] = {}
    for arm, runs in runs_by_arm.items():
        for run in runs:
            rounds = load_rounds(run.path)
            finals = final_passes_by_question(rounds)
            for qid, passed in finals.items():
                cluster_table.setdefault(qid, {}).setdefault(arm, []).append(passed)
                seed_index.setdefault(qid, {}).setdefault(arm, []).append(run.seed)
    return cluster_table, seed_index


def assert_single_memory_type(runs: Iterable[RunRecord], *, context: str = "comparison") -> str:
    """The V8 no-conflation guard (schema.md, ADR-022 (e)): every run
    handed to one comparison must share the same `memory.type`, or a
    headline (memory-off) result would be silently blended with a C'/D'
    memory-on ablation result. Returns the shared memory_type, or raises
    ConflationError naming the offending run ids."""
    runs = list(runs)
    types = {r.memory_type for r in runs}
    if len(types) > 1:
        offenders = ", ".join(f"{r.run_id}(memory={r.memory_type})" for r in runs)
        raise ConflationError(
            f"{context}: refusing to mix memory.type values {sorted(types)} in one "
            f"comparison (V8, schema.md / ADR-022 (e)) -- headline (none) runs must "
            f"never be pooled with C'/D' memory-on (faiss) runs. Offending runs: {offenders}"
        )
    if not types:
        raise ConflationError(f"{context}: no runs supplied")
    return types.pop()

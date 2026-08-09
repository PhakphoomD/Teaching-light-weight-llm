"""Every published number, recomputed from committed evidence.

The previous figure script hand-typed its numbers out of the write-up (now `docs/EXPERIMENT_RESULTS.md`),
which made the charts a transcription of a document rather than a reading of
the logs -- and left `fig6` printing rounded literals for two quantities the
same script was reading live elsewhere. This module removes the manual hop:
a figure asks for a result, the result is computed here from the artifact.

Three classes of source, all committed, all labelled on the `Measurement`:

  runs/<study>/<condition>__seed<N>__<ts>/{summary,rounds}.jsonl
      framework runs (Track A, MedQuAD RAG, fair tests, student prompt)
  runs/rag-wixqa/<step>/seed<N>.jsonl  + retrieval_log.jsonl
      the standalone WixQA study -- one judged record per (question, seed)
  reports/**/*.{json,txt}
      offline ladders and analysis printouts, already tracked as evidence

Statistics are NOT reimplemented here: `paired_cluster_bootstrap`,
`exact_mcnemar` and `wilson_interval` come from `src.tlw.analysis.stats`, the
same pre-registered functions that produced the published headlines.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from src.tlw.analysis.loaders import (
    RunRecord,
    build_cluster_table,
    discover_runs,
    final_passes_by_question,
    load_rounds,
)
from src.tlw.analysis.stats import (
    BootstrapResult,
    McNemarResult,
    WilsonInterval,
    exact_mcnemar,
    paired_cluster_bootstrap,
    wilson_interval,
)

ROOT = Path(__file__).resolve().parents[3]
RUNS = ROOT / "runs"
REPORTS = ROOT / "reports"
LOGS = ROOT / "logs" / "experiments"

BOOTSTRAP_SEED = 0  # fixed so a figure is byte-identical across regenerations
BOOTSTRAP_RESAMPLES = 10_000


class MissingEvidence(FileNotFoundError):
    """A source artifact a figure depends on is absent.

    Raised loudly rather than silently degrading: a chart drawn from partial
    evidence is worse than no chart (§0.1). Fresh clones lack `runs/` raw
    generations by design -- callers decide whether to skip or fail.
    """


# --------------------------------------------------------------------------
# the unit every figure and table is built from
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Measurement:
    """One measured quantity, with everything a reader needs to check it.

    `source` is a repo-relative path, so a caption can always answer "where
    did this number come from" without the reader trusting the caption.
    """

    objective: str  # O1..O9 -- the question this answers
    metric: str  # verbatim metric name, e.g. "pass@>=3"
    condition: str  # what was compared
    value: float
    source: str
    ci: Optional[Tuple[float, float]] = None
    p_value: Optional[float] = None
    n: Optional[int] = None
    note: str = ""
    recomputed: bool = True  # False = read from a committed printout, not re-derived

    @property
    def ci_text(self) -> str:
        if self.ci is None:
            return ""
        return f"[{self.ci[0]:+.3f}, {self.ci[1]:+.3f}]"

    @property
    def significant(self) -> Optional[bool]:
        """None when there is no interval -- absence of a CI is not evidence
        of absence of an effect, and must not render as "not significant"."""
        if self.ci is None:
            return None
        return not (self.ci[0] <= 0.0 <= self.ci[1])


@dataclass(frozen=True)
class Comparison:
    """A paired A-vs-B result: two levels, their difference, and the tests."""

    label_a: str
    label_b: str
    wilson_a: WilsonInterval
    wilson_b: WilsonInterval
    delta: BootstrapResult
    mcnemar: McNemarResult
    source: str

    @property
    def fixed(self) -> int:
        """b = passes only in arm A (the treatment) -- questions it repaired."""
        return self.mcnemar.b

    @property
    def broke(self) -> int:
        return self.mcnemar.c


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.is_file():
        raise MissingEvidence(f"missing evidence file: {path}")
    rows: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _read_json(path: Path) -> Any:
    if not path.is_file():
        raise MissingEvidence(f"missing evidence file: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def _compare(
    table: Dict[str, Dict[str, List[bool]]],
    pairs: Sequence[Tuple[bool, bool]],
    label_a: str,
    label_b: str,
    source: str,
) -> Comparison:
    """Shared tail of every paired comparison: Wilson per level, bootstrap on
    the difference, exact McNemar on the discordant pairs."""
    k_a = sum(1 for pa, _ in pairs if pa)
    k_b = sum(1 for _, pb in pairs if pb)
    return Comparison(
        label_a=label_a,
        label_b=label_b,
        wilson_a=wilson_interval(k_a, len(pairs)),
        wilson_b=wilson_interval(k_b, len(pairs)),
        delta=paired_cluster_bootstrap(
            table, label_a, label_b, n_resamples=BOOTSTRAP_RESAMPLES, seed=BOOTSTRAP_SEED
        ),
        mcnemar=exact_mcnemar(pairs, label_a, label_b),
        source=source,
    )


# ==========================================================================
# WixQA -- the standalone study (runs/rag-wixqa/<step>/seed<N>.jsonl)
# ==========================================================================

WIXQA_STEPS = {
    "no-rag": "1-no-rag",
    "rag-basic": "2-rag-basic",
    "rag-better-retriever": "3-rag-better-retriever",
    "rag-wider-context": "4-rag-wider-context",
}


def wixqa_records(step: str) -> List[Dict[str, Any]]:
    """Every judged (question, seed) record for one rung of the WixQA ladder.

    Records carry `score` (0-4 from the reference-comparing judge), and the
    RAG rungs additionally carry `gold_retrieved` / `gold_rank` -- so the
    causal gold-split is recomputable, not quoted.
    """
    step_dir = RUNS / "rag-wixqa" / WIXQA_STEPS.get(step, step)
    if not step_dir.is_dir():
        raise MissingEvidence(f"missing WixQA step directory: {step_dir}")
    rows: List[Dict[str, Any]] = []
    for seed_file in _wixqa_seed_files(step_dir):
        for row in _read_jsonl(seed_file):
            row.setdefault("seed", int(re.sub(r"\D", "", seed_file.stem) or 0))
            rows.append(row)
    if not rows:
        raise MissingEvidence(f"no judged records under {step_dir}")
    return rows


def _wixqa_seed_files(step_dir: Path) -> List[Path]:
    """One file per seed, preferring the full run file over its analysis twin.

    A step directory can hold both `seed13.jsonl` (gitignored, carries the
    generated text) and `seed13-analysis.jsonl` (tracked, same rows without it).
    Globbing `seed*.jsonl` would match both and count every record twice, so
    the seed is resolved first and the file chosen second.
    """
    by_seed: Dict[str, Path] = {}
    for path in sorted(step_dir.glob("seed*.jsonl")):
        seed = re.sub(r"\D", "", path.stem)
        is_twin = path.stem.endswith("-analysis")
        if seed not in by_seed or not is_twin:
            by_seed[seed] = path
    return [by_seed[s] for s in sorted(by_seed)]


def wixqa_gold_retrieved(step: str) -> Dict[int, bool]:
    """question index -> was the gold KB article in the retrieved top-3.

    The no-RAG rung has no retrieval of its own, so its questions are split
    using the retrieval log of the rung it is being compared against -- which
    is what makes the split a property of the *question*, not of the arm.
    """
    step_dir = RUNS / "rag-wixqa" / WIXQA_STEPS.get(step, step)
    log = step_dir / "retrieval_log.jsonl"
    if not log.is_file():
        raise MissingEvidence(f"missing retrieval log: {log}")
    return {int(r["idx"]): bool(r.get("gold_retrieved")) for r in _read_jsonl(log)}


def wixqa_hit_rate(step: str) -> Measurement:
    gold = wixqa_gold_retrieved(step)
    hits = sum(1 for v in gold.values() if v)
    return Measurement(
        objective="O5",
        metric="retrieval hit-rate@3",
        condition=step,
        value=hits / len(gold),
        n=len(gold),
        source=_rel(RUNS / "rag-wixqa" / WIXQA_STEPS.get(step, step) / "retrieval_log.jsonl"),
    )


def _wixqa_pairs(
    step_a: str,
    step_b: str,
    bar: int,
    subset: Optional[Dict[int, bool]] = None,
    want: bool = True,
) -> Tuple[Dict[str, Dict[str, List[bool]]], List[Tuple[bool, bool]]]:
    """Align two rungs on (question idx, seed) and return the bootstrap
    cluster table plus the McNemar pair list.

    `subset` restricts to questions where `gold_retrieved is want` -- the
    causal split. Alignment is on the *cell*, so an unjudged record in either
    rung drops the pair from both rather than biasing one arm.
    """
    by_cell: Dict[Tuple[int, int], Dict[str, int]] = {}
    for label, step in ((step_a, step_a), (step_b, step_b)):
        for row in wixqa_records(step):
            score = row.get("score")
            if score is None:
                continue
            idx = int(row["idx"])
            if subset is not None and subset.get(idx) is not want:
                continue
            by_cell.setdefault((idx, int(row["seed"])), {})[label] = int(score)

    table: Dict[str, Dict[str, List[bool]]] = {}
    pairs: List[Tuple[bool, bool]] = []
    for (idx, _seed), scores in sorted(by_cell.items()):
        if step_a not in scores or step_b not in scores:
            continue
        pa, pb = scores[step_a] >= bar, scores[step_b] >= bar
        table.setdefault(str(idx), {}).setdefault(step_a, []).append(pa)
        table[str(idx)].setdefault(step_b, []).append(pb)
        pairs.append((pa, pb))
    if not pairs:
        raise MissingEvidence(f"no paired cells for {step_a} vs {step_b}")
    return table, pairs


def wixqa_comparison(
    step_a: str,
    step_b: str,
    bar: int = 3,
    subset: Optional[Dict[int, bool]] = None,
    want: bool = True,
) -> Comparison:
    """Paired A-vs-B on the WixQA ladder. `step_a` is the treatment, so a
    positive delta always reads as "the change helped"."""
    table, pairs = _wixqa_pairs(step_a, step_b, bar, subset=subset, want=want)
    return _compare(table, pairs, step_a, step_b, _rel(RUNS / "rag-wixqa"))


def wixqa_pass_rate(step: str, bar: int = 3) -> WilsonInterval:
    scores = [r["score"] for r in wixqa_records(step) if r.get("score") is not None]
    return wilson_interval(sum(1 for s in scores if s >= bar), len(scores))


def wixqa_score_distribution(step: str) -> Dict[int, int]:
    dist: Dict[int, int] = {s: 0 for s in range(5)}
    for row in wixqa_records(step):
        if row.get("score") is not None:
            dist[int(row["score"])] = dist.get(int(row["score"]), 0) + 1
    return dist


def wixqa_mean_score(step: str) -> float:
    scores = [r["score"] for r in wixqa_records(step) if r.get("score") is not None]
    return sum(scores) / len(scores)


def wixqa_catastrophe_rate(step: str) -> float:
    """Share scoring <=1 -- "not merely incomplete, actively unhelpful"."""
    scores = [r["score"] for r in wixqa_records(step) if r.get("score") is not None]
    return sum(1 for s in scores if s <= 1) / len(scores)


def wixqa_answer_words(step: str) -> float:
    """Mean answer length, in words, for one rung of the WixQA ladder.

    This is the one published quantity that reads the generated answers rather
    than the scores. Those answers were pruned from disk after the scoring
    columns were extracted, so when they are absent the value is read from
    `reports/rag-wixqa/answer-length-by-rung.json`, which records what was
    computed while they were present and says so.

    Silence would be worse than either: before this fallback existed the
    computation returned 0.0 for every rung and two published tables quietly
    printed zeros. It raises now rather than averaging an empty list.
    """
    lengths = [len((r.get("answer") or "").split()) for r in wixqa_records(step)]
    if lengths and any(lengths):
        return sum(lengths) / len(lengths)

    cached = ROOT / "reports" / "rag-wixqa" / "answer-length-by-rung.json"
    if cached.is_file():
        payload = json.loads(cached.read_text(encoding="utf-8"))
        key = WIXQA_STEPS.get(step, step)
        if key in payload:
            return float(payload[key])
    raise MissingEvidence(
        f"no answer text for WixQA step {step!r} and no cached length in {cached}"
    )


SELF_REFINE_PILOT = "pilots/5-rag-plus-self-refine"


def wixqa_loop_cells() -> List[Dict[str, Any]]:
    """The Loop+RAG study, paired against the right comparator.

    Subtle and worth stating: the single-pass side of this comparison is the
    seed-42 slice of the full `4-rag-wider-context` run restricted to the
    gold-retrieved questions -- NOT the similarly-named
    `pilots/4-rag-wider-context-goldonly`, which is an earlier and separate
    pilot of the grounding change and sits four points lower. Pairing against
    that one instead turns a published -0.015 into a +0.045, i.e. flips the
    study's conclusion. The two are distinguished here by construction so the
    mistake cannot be made silently.

    Each returned cell also carries the model's own round-1 verdict on whether
    its answer was already complete, which is what makes the "could it gate
    itself?" question answerable from the log rather than quoted.
    """
    refined = {int(r["idx"]): r for r in wixqa_records(SELF_REFINE_PILOT)}
    cells: List[Dict[str, Any]] = []
    for row in wixqa_records("rag-wider-context"):
        idx = int(row["idx"])
        if int(row["seed"]) != 42 or not row.get("gold_retrieved") or idx not in refined:
            continue
        ref = refined[idx]
        rounds = ref.get("rounds") or [{}]
        cells.append(
            {
                "idx": idx,
                "single": int(row["score"]),
                "refined": int(ref["score"]),
                "self_complete": str(rounds[0].get("self_complete", "")).lower() == "true",
            }
        )
    if not cells:
        raise MissingEvidence("no paired cells for the Loop+RAG study")
    return cells


def wixqa_loop_comparison(bar: int = 3) -> Comparison:
    cells = wixqa_loop_cells()
    table: Dict[str, Dict[str, List[bool]]] = {}
    pairs: List[Tuple[bool, bool]] = []
    for cell in cells:
        pa, pb = cell["refined"] >= bar, cell["single"] >= bar
        table[str(cell["idx"])] = {"with refinement": [pa], "single pass": [pb]}
        pairs.append((pa, pb))
    return _compare(
        table, pairs, "with refinement", "single pass", _rel(RUNS / "rag-wixqa")
    )


def wixqa_loop_by_prior_score() -> Dict[int, Dict[str, float]]:
    """What refinement did, bucketed by what the answer already scored.

    This is the shape that explains an aggregate null: an intervention can
    lift the answers that were wrong and damage the ones that were right, and
    net to zero. Only the bucketed view shows both halves.
    """
    buckets: Dict[int, Dict[str, float]] = {}
    for cell in wixqa_loop_cells():
        b = buckets.setdefault(
            cell["single"], {"n": 0, "delta_sum": 0.0, "improved": 0, "worsened": 0}
        )
        b["n"] += 1
        b["delta_sum"] += cell["refined"] - cell["single"]
        if cell["refined"] > cell["single"]:
            b["improved"] += 1
        elif cell["refined"] < cell["single"]:
            b["worsened"] += 1
    for b in buckets.values():
        b["mean_delta"] = b["delta_sum"] / b["n"]
    return dict(sorted(buckets.items()))


def wixqa_loop_policy_ladder(bar: int = 3, gate_max: int = 2) -> Dict[str, WilsonInterval]:
    """Four refinement policies scored on the same cells.

    `oracle` refines only where the single-pass answer already scored at or
    below `gate_max`. It is not implementable -- it needs the score it is
    trying to predict -- and exists to measure the headroom a reliable gate
    would unlock. The last policy is the implementable version of the same
    idea, using the model's own round-1 judgement of whether it was done; the
    gap between the two is the cost of that judgement being unreliable.
    """
    cells = wixqa_loop_cells()
    n = len(cells)

    def rate(pick) -> WilsonInterval:
        return wilson_interval(sum(1 for c in cells if pick(c) >= bar), n)

    return {
        "single pass, never refine": rate(lambda c: c["single"]),
        "always refine": rate(lambda c: c["refined"]),
        "refine only weak answers (oracle)": rate(
            lambda c: c["refined"] if c["single"] <= gate_max else c["single"]
        ),
        "refine when the model says it is not done": rate(
            lambda c: c["single"] if c["self_complete"] else c["refined"]
        ),
    }


def wixqa_self_assessment_rate() -> Tuple[int, int]:
    """How often the model declared its first answer already complete."""
    cells = wixqa_loop_cells()
    return sum(1 for c in cells if c["self_complete"]), len(cells)


def wixqa_conditional_pass(step: str, bar: int = 3) -> Tuple[WilsonInterval, WilsonInterval]:
    """P(pass | gold retrieved) and P(pass | gold missed) for one rung.

    This pair is the mechanism behind the dose-response: a better retriever
    moves how OFTEN gold is found, while the payoff when it is found barely
    moves. A figure that shows only the aggregate hides that.
    """
    gold = wixqa_gold_retrieved(step)
    got: List[bool] = []
    missed: List[bool] = []
    for row in wixqa_records(step):
        if row.get("score") is None:
            continue
        (got if gold.get(int(row["idx"])) else missed).append(row["score"] >= bar)
    return (
        wilson_interval(sum(got), len(got)),
        wilson_interval(sum(missed), len(missed)),
    )


# ==========================================================================
# Framework runs -- Track A, MedQuAD RAG, fair tests, student prompt
# ==========================================================================


def _condition(run: RunRecord) -> str:
    """`2-self-refine__seed42__20260715T061350Z` -> `2-self-refine`.

    Keyed on the condition, not the config stem: a rename of the YAML must
    not silently change which runs a comparison pools (structure.md §E).
    """
    return run.run_id.split("__")[0]


def study_runs(study: str) -> Dict[str, List[RunRecord]]:
    """{condition: [run per seed]} for one study directory.

    `discover_runs` scans one level deep, so `pilots/` and subset directories
    are structurally excluded from a headline -- the guarantee ADR-034 built
    into the layout rather than leaving to a filter someone must remember.
    """
    study_dir = RUNS / study
    if not study_dir.is_dir():
        raise MissingEvidence(f"missing study directory: {study_dir}")
    grouped: Dict[str, List[RunRecord]] = {}
    for run in discover_runs(study_dir):
        grouped.setdefault(_condition(run), []).append(run)
    if not grouped:
        raise MissingEvidence(f"no runs with a summary.jsonl under {study_dir}")
    return grouped


def study_pass_rate(study: str, condition: str) -> WilsonInterval:
    """Pooled pass rate across that condition's seeds, from `rounds.jsonl`.

    Recomputed per question rather than averaging the per-run `pass_rate`
    field, so the n matches what the CI is actually built on.
    """
    runs = study_runs(study).get(condition)
    if not runs:
        raise MissingEvidence(f"{study}: no runs for condition {condition!r}")
    passes = [p for run in runs for p in final_passes_by_question(load_rounds(run.path)).values()]
    return wilson_interval(sum(passes), len(passes))


def study_comparison(study: str, cond_a: str, cond_b: str) -> Comparison:
    """Paired comparison between two conditions of one study.

    Deliberately does NOT call `assert_single_memory_type`: for the RAG
    studies, crossing `memory.type` none->rag IS the experiment. The V8 guard
    exists to stop a headline arm being pooled with a memory-on ablation of
    the same arm, which is a different mistake.
    """
    grouped = study_runs(study)
    for cond in (cond_a, cond_b):
        if cond not in grouped:
            raise MissingEvidence(
                f"{study}: condition {cond!r} not found (have: {sorted(grouped)})"
            )
    table, _seed_index = build_cluster_table({c: grouped[c] for c in (cond_a, cond_b)})

    pairs: List[Tuple[bool, bool]] = []
    for _qid, arms in sorted(table.items()):
        if cond_a not in arms or cond_b not in arms:
            continue
        for pa, pb in zip(arms[cond_a], arms[cond_b]):
            pairs.append((pa, pb))
    if not pairs:
        raise MissingEvidence(f"{study}: no paired questions between {cond_a} and {cond_b}")
    return _compare(table, pairs, cond_a, cond_b, _rel(RUNS / study))


def study_summary_field(study: str, condition: str, *keys: str) -> List[Any]:
    """Pull a nested `summary.jsonl` value for each seed of a condition --
    e.g. reference_match, avg_rounds, teacher_calls, token totals."""
    out: List[Any] = []
    for run in study_runs(study).get(condition, []):
        node: Any = run.summary
        for key in keys:
            if not isinstance(node, dict):
                node = None
                break
            node = node.get(key)
        out.append(node)
    return out


def study_outcome_by_reliability(
    study: str, cond_treatment: str, cond_baseline: str
) -> Dict[str, Dict[str, int]]:
    """Repairs and regressions bucketed by how reliably the baseline already
    answered each question across its seeds.

    The aggregate null hides a gradient, and the gradient is the finding: an
    intervention that repairs what the model never knew while damaging what it
    reliably knew is not "no effect", it is two effects of similar size. Three
    buckets -- never right, sometimes right, always right -- because a question
    the baseline got in 1 of 3 seeds is neither a knowledge gap nor a solid
    answer, and collapsing it into either end overstates the contrast.
    """
    grouped = study_runs(study)
    table, _ = build_cluster_table(
        {c: grouped[c] for c in (cond_treatment, cond_baseline) if c in grouped}
    )
    buckets: Dict[str, Dict[str, int]] = {
        "never": {"fixed": 0, "broke": 0, "questions": 0},
        "sometimes": {"fixed": 0, "broke": 0, "questions": 0},
        "always": {"fixed": 0, "broke": 0, "questions": 0},
    }
    for _qid, arms in table.items():
        if cond_treatment not in arms or cond_baseline not in arms:
            continue
        base, treat = arms[cond_baseline], arms[cond_treatment]
        hits = sum(base)
        key = "never" if hits == 0 else "always" if hits == len(base) else "sometimes"
        buckets[key]["questions"] += 1
        for pb, pt in zip(base, treat):
            if pt and not pb:
                buckets[key]["fixed"] += 1
            elif pb and not pt:
                buckets[key]["broke"] += 1
    return buckets


def study_outcome_split(study: str, cond_treatment: str, cond_baseline: str) -> Dict[str, int]:
    """Where a treatment's wins and losses land, by how reliably the baseline
    already answered the question.

    The aggregate null on MedQuAD hides this: RAG repaired questions the
    baseline never got and broke ones it always got. `broke_easy` counts
    breaks on questions the baseline passed in EVERY seed.
    """
    grouped = study_runs(study)
    table, _ = build_cluster_table(
        {c: grouped[c] for c in (cond_treatment, cond_baseline) if c in grouped}
    )
    out = {"fixed": 0, "broke": 0, "broke_easy": 0, "fixed_hard": 0, "both_pass": 0, "both_fail": 0}
    for _qid, arms in table.items():
        if cond_treatment not in arms or cond_baseline not in arms:
            continue
        base, treat = arms[cond_baseline], arms[cond_treatment]
        always_passed = all(base)
        never_passed = not any(base)
        for pb, pt in zip(base, treat):
            if pt and pb:
                out["both_pass"] += 1
            elif not pt and not pb:
                out["both_fail"] += 1
            elif pt and not pb:
                out["fixed"] += 1
                if never_passed:
                    out["fixed_hard"] += 1
            else:
                out["broke"] += 1
                if always_passed:
                    out["broke_easy"] += 1
    return out


# ==========================================================================
# Offline evidence already committed under reports/
# ==========================================================================


def retriever_ladder() -> Dict[str, Dict[str, Any]]:
    """7 retriever variants x hit-rate@{1,3,5,10} + MRR + build seconds.

    Offline, zero LLM calls -- this is the cheap measurement that decided
    which single variant was worth an end-to-end run.
    """
    return _read_json(REPORTS / "rag-wixqa" / "retriever-hitrate.json")


def coverage_ladder() -> Dict[str, Dict[str, Any]]:
    """The 2x2 of grounding budget x placement, scored by how much of the
    expert answer's content actually reaches the prompt."""
    return _read_json(REPORTS / "rag-wixqa" / "context-window-coverage.json")


def lora_result() -> Dict[str, Any]:
    return _read_json(REPORTS / "lora-medquad" / "fine-tuned-vs-original.json")


def demo_showcase() -> List[Dict[str, Any]]:
    return _read_jsonl(REPORTS / "rag-wixqa" / "demo-showcase.jsonl")


_PRINTOUT_PATTERNS = {
    "reference_coverage": re.compile(
        r"(?P<a>[\w-]+)=(?P<va>[\d.]+)\s+(?P<b>[\w-]+)=(?P<vb>[\d.]+)\s+delta=(?P<d>[+-][\d.]+)\s+"
        r"\[(?P<lo>[+-][\d.]+),\s*(?P<hi>[+-][\d.]+)\]"
    ),
    # both sides of the arrow are prefixed by their condition name, so the
    # pattern skips over words between the two percentages rather than
    # assuming they sit either side of a bare arrow.
    "extraction": re.compile(r"extraction ratio[^\n]*?(\d+)%[^\n]*?(\d+)%"),
    "length": re.compile(r"answer length:\s*(\d+)\s*->\s*(\d+)\s*words"),
}


def analysis_printout(relative: str) -> Dict[str, Any]:
    """Parse one committed analysis printout under `reports/`.

    Two of its quantities -- reference-coverage and the extraction ratio --
    are content-overlap metrics computed by the study scripts at analysis
    time and not derivable from the judged records alone, so they are read
    rather than recomputed. Everything returned here is stamped
    `recomputed=False` by callers so a caption never overstates its
    provenance.
    """
    path = REPORTS / relative
    if not path.is_file():
        raise MissingEvidence(f"missing analysis printout: {path}")
    text = path.read_text(encoding="utf-8")
    out: Dict[str, Any] = {"source": _rel(path)}

    cov = _PRINTOUT_PATTERNS["reference_coverage"].search(text)
    if cov:
        out["coverage_before"] = float(cov.group("va"))
        out["coverage_after"] = float(cov.group("vb"))
        out["coverage_delta"] = float(cov.group("d"))
        out["coverage_ci"] = (float(cov.group("lo")), float(cov.group("hi")))

    ext = _PRINTOUT_PATTERNS["extraction"].search(text)
    if ext:
        out["extraction_before"] = int(ext.group(1)) / 100
        out["extraction_after"] = int(ext.group(2)) / 100

    length = _PRINTOUT_PATTERNS["length"].search(text)
    if length:
        out["words_before"] = int(length.group(1))
        out["words_after"] = int(length.group(2))
    return out


# ==========================================================================
# V1 -- the pre-renovation logs, kept immutable under logs/experiments/
# ==========================================================================


# ==========================================================================
# The stages before the experiments: the dataset, and the instrument
# ==========================================================================

DATA_CLEAN = ROOT / "data" / "clean"


def cleaning_reports() -> Dict[str, Dict[str, Any]]:
    """Per-domain before/after from the cleaning pipeline.

    Presented because the result rests on it: a pass rate measured against a
    noisy reference is a measurement of the noise. Every downstream number
    inherits whatever this stage left behind.
    """
    out: Dict[str, Dict[str, Any]] = {}
    for path in sorted(DATA_CLEAN.glob("*_report.json")):
        out[path.stem.replace("_report", "")] = _read_json(path)
    if not out:
        raise MissingEvidence(f"no cleaning reports under {DATA_CLEAN}")
    return out


def readiness(target: str = "rag") -> Dict[str, Any]:
    """The readiness score of the domain the experiments actually used."""
    matches = sorted(DATA_CLEAN.glob(f"*_readiness_{target}.json"))
    if not matches:
        raise MissingEvidence(f"no readiness report for target {target!r}")
    return _read_json(matches[0])


def judge_calibration() -> List[Dict[str, Any]]:
    """Every judge-calibration probe that was run, with its verdict.

    Both candidate judges failed. That is reported rather than buried, and the
    response -- raise the pass bar and hold one judge fixed across all arms --
    is a protocol change made *because* of a failure, not a probe retuned
    until it passed. The strongest signal here is the `plausible_wrong` column:
    a judge that passes deliberately-wrong answers cannot certify correctness.

    The two candidates were probed by two different script versions and their
    files use different key names -- `summary`/`judge_model` for one,
    `local_summary`/`local_judge_model` for the other. Both shapes are read
    here, because reading only one silently dropped the *more* damning of the
    two results while the caption still said "neither candidate passed".
    """
    probes: List[Dict[str, Any]] = []
    for path in sorted((RUNS / "judge-calibration").rglob("probe_*.json")):
        raw = _read_json(path)
        summary = raw.get("summary") or raw.get("local_summary") or {}
        per_class = summary.get("per_class", {})
        if int(raw.get("n", 0)) < 40 or not per_class:
            continue  # budget-truncated probes are not comparable; skip, don't average
        seed_match = re.search(r"seed(\d+)", path.stem)
        probes.append(
            {
                "judge": raw.get("judge_model") or raw.get("local_judge_model") or path.parent.name,
                "seed": raw.get("seed") or (int(seed_match.group(1)) if seed_match else None),
                "n_per_class": per_class.get("good", {}).get("n"),
                "good": per_class.get("good", {}).get("pass_rate"),
                "wrong": per_class.get("wrong", {}).get("pass_rate"),
                "truncated": per_class.get("truncated", {}).get("pass_rate"),
                "plausible_wrong": per_class.get("plausible_wrong", {}).get("pass_rate"),
                "discrimination": summary.get("discrimination_good_minus_wrong"),
                "kappa": raw.get("kappa_vs_groq70b") or raw.get("kappa"),
                "passed_gate": bool(raw.get("kappa_gate_pass")),
                "source": _rel(path),
            }
        )
    if not probes:
        raise MissingEvidence("no full-size judge calibration probes found")
    if len({p["judge"] for p in probes}) < 2:
        raise MissingEvidence(
            "only one candidate judge was read, but two were probed -- a probe schema is being "
            f"silently dropped (found: {sorted({p['judge'] for p in probes})})"
        )
    return sorted(probes, key=lambda p: (str(p["judge"]), p["seed"] or 0))


def track_a_bar_sensitivity() -> Dict[str, Dict[int, float]]:
    """Each loop arm's pass rate at both candidate bars.

    The reason the headline uses "correct AND complete" rather than "correct":
    at the lower bar every arm passes almost everything, so the comparison
    between arms has no room to show a difference and would have returned a
    null by construction rather than by evidence. Recomputed from the raw
    judge scores in `rounds.jsonl`, so the choice is inspectable rather than
    asserted.
    """
    out: Dict[str, Dict[int, float]] = {}
    for condition, runs in study_runs("teaching-loop-medquad").items():
        finals: Dict[str, int] = {}
        for run in runs:
            for row in load_rounds(run.path):
                qid, score = row.get("question_id"), row.get("score")
                if qid is not None and score is not None:
                    finals[f"{run.run_id}:{qid}"] = int(score)
        if finals:
            scores = list(finals.values())
            out[condition] = {
                bar: sum(1 for s in scores if s >= bar) / len(scores) for bar in (3, 4)
            }
    return out


def kb_article_lengths() -> List[int]:
    """Character length of every knowledge-base article.

    The reason embedding whole articles loses: the encoder reads roughly the
    first 256 tokens, and most of these articles are far longer than that, so
    a whole-article vector describes an introduction rather than a document.
    """
    path = ROOT / "data" / "external" / "wixqa" / "kb_corpus.jsonl"
    if not path.is_file():
        raise MissingEvidence(f"missing KB corpus: {path} (run scripts/dataset/fetch_wixqa.py)")
    return [len(row.get("contents") or "") for row in _read_jsonl(path)]


def gold_article_truncation(budget_chars: int = 900) -> Dict[str, float]:
    """How much of each answer-bearing article the original window could show.

    Recomputed rather than quoted: the caption for the grounding figure used to
    state a median length and a truncation share that appear in no artifact the
    figure cites -- correct numbers with no reproducible source, which is the
    same defect as a wrong one, only harder to notice.
    """
    lengths_by_id = {}
    kb = ROOT / "data" / "external" / "wixqa" / "kb_corpus.jsonl"
    if not kb.is_file():
        # The knowledge base is third-party data (MIT, 50 MB) that a clone
        # fetches rather than carries, so this is the one published value that
        # cannot be recomputed from what the repository ships. The cached
        # result is committed instead, and is recomputed and overwritten
        # whenever the corpus is present -- so the two cannot drift apart
        # silently, and a reader without the corpus still gets the number with
        # its provenance attached.
        cached = ROOT / "reports" / "rag-wixqa" / "gold-article-truncation.json"
        if cached.is_file():
            payload = json.loads(cached.read_text(encoding="utf-8"))
            if int(payload.get("budget_chars", -1)) == int(budget_chars):
                return {k: v for k, v in payload.items() if not k.startswith("_")}
            raise MissingEvidence(
                f"cached truncation is for budget_chars={payload.get('budget_chars')}, "
                f"asked for {budget_chars}; fetch the KB corpus to recompute"
            )
        raise MissingEvidence(f"missing KB corpus: {kb}")
    for row in _read_jsonl(kb):
        lengths_by_id[row["id"]] = len(row.get("contents") or "")

    # Counted per ARTICLE, not per question: some questions have more than one
    # answer-bearing article (133 questions, 177 articles), and the published
    # figure is a statement about articles. Taking one per question instead
    # shifts the median by ~140 characters.
    lengths = []
    for row in _read_jsonl(RUNS / "rag-wixqa" / "4-rag-wider-context" / "retrieval_log.jsonl"):
        if not row.get("gold_retrieved"):
            continue
        lengths.extend(
            lengths_by_id[gid] for gid in (row.get("gold_article_ids") or []) if gid in lengths_by_id
        )
    if not lengths:
        raise MissingEvidence("no gold-article lengths could be resolved")
    lengths.sort()
    return {
        "median_chars": lengths[len(lengths) // 2],
        "share_truncated": sum(1 for v in lengths if v > budget_chars) / len(lengths),
        "n_articles": len(lengths),
        "budget_chars": budget_chars,
    }


def retriever_levers() -> Dict[str, float]:
    """Which change did the work: splitting articles, or a better encoder.

    Reported separately because the intuitive answer (a stronger embedding
    model) is the smaller of the two.
    """
    ladder = retriever_ladder()
    base = ladder["minilm_whole"]["hitrate"]["3"]
    return {
        "splitting articles into chunks": ladder["minilm_chunk"]["hitrate"]["3"] - base,
        "a stronger encoder": ladder["bge_whole"]["hitrate"]["3"] - base,
        "both together": ladder["bge_chunk"]["hitrate"]["3"] - base,
    }


def gold_rank_curves() -> Dict[str, Dict[int, float]]:
    """Cumulative hit rate against k for every retriever variant."""
    ladder = retriever_ladder()
    return {
        name: {int(k): v for k, v in payload["hitrate"].items() if k != "mrr"}
        for name, payload in ladder.items()
        if name != "_meta"
    }


# ==========================================================================
# Reliability, selectivity, cost -- the questions a deployment would ask
# ==========================================================================


RELIABILITY = "rag-medquad-reliability/hard-questions-only"
MEDQUAD_STUDY = "rag-medquad"


def reliability_metrics(study: str = RELIABILITY) -> Dict[str, Dict[str, float]]:
    """Does retrieval make an answer *dependable*, not just more often right?

    Three different questions of the same runs: per-attempt accuracy, whether
    the model got it right at least once across seeds, and whether it got it
    right *every* time. A product cares about the third. Note the set was
    selected on prior failure, so only the difference between arms carries
    meaning, never either level on its own.

    Defaults to the 35-question 5-seed set, which is the one the published
    analysis used. A larger 125-question 8-seed sweep also sits under
    `runs/rag-medquad-reliability/` but was judged with a different model and
    returns levels far below every other study here; it is deliberately NOT
    pooled with this one, and NOT quietly dropped either -- it is named in the
    report table as unfinished and not comparable. Mixing the two would blend
    two instruments into one number.
    """
    grouped = study_runs(study)
    out: Dict[str, Dict[str, float]] = {}
    for condition, runs in grouped.items():
        per_question: Dict[str, List[bool]] = {}
        for run in runs:
            for qid, passed in final_passes_by_question(load_rounds(run.path)).items():
                per_question.setdefault(qid, []).append(passed)
        attempts = [p for outcomes in per_question.values() for p in outcomes]
        out[condition] = {
            "per_attempt": sum(attempts) / len(attempts),
            "ever_right": sum(1 for o in per_question.values() if any(o)) / len(per_question),
            "always_right": sum(1 for o in per_question.values() if all(o)) / len(per_question),
            "questions": len(per_question),
            "seeds": len(runs),
        }
    return out


def genuine_gap_questions() -> set:
    """Questions the model never once answered correctly without retrieval.

    Recomputed rather than read from a stored list, so it cannot drift from the
    runs it is derived from: a question qualifies only if the baseline failed
    it in every one of its three seeds.
    """
    grouped = study_runs(MEDQUAD_STUDY)
    gaps = set()
    per_question: Dict[str, List[bool]] = {}
    for run in grouped.get("small-model-no-rag", []):
        for qid, passed in final_passes_by_question(load_rounds(run.path)).items():
            per_question.setdefault(qid, []).append(passed)
    for qid, outcomes in per_question.items():
        if outcomes and not any(outcomes):
            gaps.add(qid)
    return gaps


def reliability_on_genuine_gaps() -> Dict[str, Dict[str, float]]:
    """The reliability probe restricted to real knowledge gaps.

    The broader hard-tail set mixes questions the model sometimes got right
    with ones it never did, and retrieval behaves differently on each. This is
    the subset where a knowledge gap actually exists -- and the only place in
    the project where retrieval made answers *dependable* rather than merely
    more often right: none of them were answered correctly on all five attempts
    without retrieval, and several were with it.
    """
    gaps = genuine_gap_questions()
    out: Dict[str, Dict[str, float]] = {}
    for condition, runs in study_runs(RELIABILITY).items():
        per_question: Dict[str, List[bool]] = {}
        for run in runs:
            for qid, passed in final_passes_by_question(load_rounds(run.path)).items():
                if qid in gaps:
                    per_question.setdefault(qid, []).append(passed)
        if not per_question:
            continue
        attempts = [p for o in per_question.values() for p in o]
        out[condition] = {
            "per_attempt": sum(attempts) / len(attempts),
            "ever_right": sum(1 for o in per_question.values() if any(o)) / len(per_question),
            "always_right": sum(1 for o in per_question.values() if all(o)) / len(per_question),
            "always_right_count": sum(1 for o in per_question.values() if all(o)),
            "questions": len(per_question),
            "seeds": len(runs),
        }
    return out


def selective_oracle(study: str, cond_treatment: str, cond_baseline: str) -> Dict[str, float]:
    """What a perfect "when should I retrieve?" gate would be worth.

    Applies the treatment only where the baseline falls short. Neither variant
    is implementable -- both need the outcome they are predicting -- and they
    exist to separate "the intervention is useless" from "the intervention is
    useful but applied indiscriminately". On both testbeds the answer was the
    second, which is why the missing piece is a gate.

    Two bounds, because they answer different questions and differ by a point:

    - *per attempt* takes the better of the two outcomes on every single
      attempt. It is the absolute ceiling and the figure published in
      `docs/EXPERIMENT_RESULTS.md §7.2`, and it assumes a gate that can see the future of
      one specific generation.
    - *per question* decides once per question, from whether the baseline ever
      struggled with it across seeds. Still not implementable, but far closer
      to a gate anyone could actually build -- and it is the more honest
      target, so both are reported.
    """
    grouped = study_runs(study)
    table, _ = build_cluster_table({c: grouped[c] for c in (cond_treatment, cond_baseline)})
    baseline_hits = treatment_hits = per_attempt = per_question = total = 0
    for _qid, arms in table.items():
        if cond_treatment not in arms or cond_baseline not in arms:
            continue
        base, treat = arms[cond_baseline], arms[cond_treatment]
        struggled = not all(base)
        for pb, pt in zip(base, treat):
            total += 1
            baseline_hits += int(pb)
            treatment_hits += int(pt)
            per_attempt += int(pb or pt)
            per_question += int(pt if struggled else pb)
    return {
        "baseline": baseline_hits / total,
        "always apply": treatment_hits / total,
        "gate per question (the buildable target)": per_question / total,
        "gate per attempt (the absolute ceiling)": per_attempt / total,
        "n": total,
    }


def run_cost(study: str, condition: str) -> Dict[str, Any]:
    """Wall-clock, calls and tokens for one condition, summed over its seeds.

    Included because "runs on a laptop for nothing" is a claim, and a claim
    needs a number. Cloud spend was zero: the student and the index are local;
    only the judge used a free-tier API.
    """
    totals = {"seconds": 0.0, "student_calls": 0, "student_tokens": 0, "judge_calls": 0,
              "teacher_calls": 0, "teacher_tokens": 0, "seeds": 0}
    for run in study_runs(study).get(condition, []):
        totals["seeds"] += 1
        totals["seconds"] += float(run.summary.get("elapsed_seconds") or 0)
        for role in ("student", "judge", "teacher"):
            block = run.summary.get(f"{role}_calls")
            if isinstance(block, dict):
                totals[f"{role}_calls"] = totals.get(f"{role}_calls", 0) + int(block.get("calls", 0))
                if f"{role}_tokens" in totals:
                    totals[f"{role}_tokens"] += int(block.get("tokens", 0))
    return totals


def faithfulness(study: str, condition: str) -> Optional[Dict[str, Any]]:
    """The groundedness diagnostic, with its null rate attached.

    The null rate is the point: the metric could not be parsed for most
    answers at this judge quality, so it was kept as a diagnostic and never
    allowed near the pass decision. A mean quoted without it would look like
    a result.
    """
    parsed = nulls = 0
    weighted = 0.0
    for run in study_runs(study).get(condition, []):
        block = (run.summary.get("metrics") or {}).get("faithfulness")
        if isinstance(block, dict) and block.get("mean") is not None:
            n = int(block.get("n", 0))
            parsed += n
            nulls += int(block.get("null", 0))
            weighted += float(block["mean"]) * n
    if not parsed:
        return None
    # Aggregate over every seed, weighted by how many answers each seed
    # actually parsed. Returning the first seed's value instead would report a
    # third of the evidence as if it were all of it -- and because run
    # directories sort lexically, "seed123" would be the one that won.
    return {
        "mean": weighted / parsed,
        "parsed": parsed,
        "null": nulls,
        "null_rate": nulls / (parsed + nulls),
        "seeds": len(study_runs(study).get(condition, [])),
    }


def grounding_filtered(study: str, condition: str) -> int:
    """Retrieved passages dropped at run time for sharing wording with the
    held-out answer -- the anti-leak filter, counted and reported."""
    return sum(
        int(run.summary.get("grounding_filtered_total") or 0)
        for run in study_runs(study).get(condition, [])
    )


def test_count() -> int:
    """How many tests the suite collects, asked of pytest rather than typed.

    A hand-written count is exactly the kind of number that rots: it was
    already stale by 35 the first time it was written down. Collection is
    cheap (no test bodies run) and keeps the claim true by construction.
    """
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    # `-q` collection prints one `<path>: <count>` line per test file.
    counts = re.findall(r"^\S+\.py:\s*(\d+)\s*$", result.stdout, flags=re.MULTILINE)
    if not counts:
        raise MissingEvidence(
            f"could not read a test count from pytest --collect-only (exit {result.returncode})"
        )
    return sum(int(c) for c in counts)


def v1_phase_summaries(phase: str) -> List[Dict[str, Any]]:
    """One phase's committed `summary.jsonl`.

    These are the logs the retired write-up was supposed to be reporting.
    Reading them is how the retraction table states what the runs actually
    produced instead of what the document claimed.
    """
    return _read_jsonl(LOGS / phase / "summary.jsonl")


def v1_metric_weights() -> Dict[str, float]:
    """What V1's composite score actually weighted.

    Recorded in `logs/experiments/phase6/configs/*.yml` and reproduced in the
    leakage census: three of the four components compare the answer against
    the reference, so 70% of the score measured resemblance rather than
    correctness. This is a fact about the *metric*, which is why it can be
    charted while V1's pass rates cannot share an axis with V2's.
    """
    return {
        "comparison judge (sees the reference)": 0.35,
        "semantic similarity to reference": 0.25,
        "ROUGE-L against reference": 0.10,
        "blind judge (correctness only)": 0.30,
    }


def v1_phase_table() -> List[Dict[str, Any]]:
    """Every pre-renovation phase, as its own logs record it.

    Kept because the earlier work is part of the record, not an embarrassment
    to be deleted: it is where the dataset, the loop and the prompt styles came
    from, and its failure is what defined the rebuild's constraints. What is
    retired is the *reporting*, not the runs.
    """
    described = {
        "phase0": "warm-up: does the loop run end to end",
        "phase1": "memory on vs off",
        "phase2": "three teacher-feedback styles",
        "phase3": "hyper-parameter grid",
        "phase4": "does it transfer across medical domains",
        "phase5": "baseline vs the full optimised system",
        "phase6": "memory seeded with the reference answers",
    }
    rows: List[Dict[str, Any]] = []
    for phase, purpose in described.items():
        path = LOGS / phase / "summary.jsonl"
        if not path.is_file():
            continue
        records = _read_jsonl(path)
        rates = [r.get("pass_rate") for r in records if r.get("pass_rate") is not None]
        tokens = sum(int(r.get("student_teacher_tokens") or 0) for r in records)
        rows.append(
            {
                "phase": phase,
                "purpose": purpose,
                "runs": len(records),
                "questions": records[0].get("num_questions") if records else None,
                "pass_rate_range": (min(rates), max(rates)) if rates else None,
                "tokens": tokens,
                "source": _rel(path),
            }
        )
    return rows


LITERATURE: List[Dict[str, str]] = [
    # key, authors, year, title, venue, id, role, tested, verdict
    dict(key="lewis2020", authors="Lewis, P., Perez, E., Piktus, A., et al.", year="2020",
         title="Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks",
         venue="NeurIPS 2020", id="arXiv:2005.11401", role="architecture",
         tested="the architecture implemented here", verdict="used"),
    dict(key="ovadia2024", authors="Ovadia, O., Brief, M., Mishaeli, M., Elisha, O.", year="2024",
         title="Fine-Tuning or Retrieval? Comparing Knowledge Injection in LLMs",
         venue="EMNLP 2024", id="arXiv:2312.05934", role="claim tested",
         tested="retrieval +0.152 where a gap existed; fine-tuning −0.292",
         verdict="**confirmed**"),
    dict(key="zhou2023", authors="Zhou, C., Liu, P., Xu, P., et al.", year="2023",
         title="LIMA: Less Is More for Alignment", venue="NeurIPS 2023",
         id="arXiv:2305.11206", role="claim tested",
         tested="the adapter transferred style and cost completeness (−0.292)",
         verdict="**confirmed**"),
    dict(key="madaan2023", authors="Madaan, A., Tandon, N., Gupta, P., et al.", year="2023",
         title="Self-Refine: Iterative Refinement with Self-Feedback", venue="NeurIPS 2023",
         id="arXiv:2303.17651", role="claim tested",
         tested="held on a saturated domain (+0.091); did not transfer on top of retrieval at 3B "
                "(−0.015, p=0.77)",
         verdict="**contradicted at this scale**"),
    dict(key="huang2024", authors="Huang, J., Chen, X., Mishra, S., et al.", year="2024",
         title="Large Language Models Cannot Self-Correct Reasoning Yet", venue="ICLR 2024",
         id="arXiv:2310.01798", role="claim tested",
         tested="the 3B called itself complete 79/133 times; oracle gate +0.038, its own gate +0.000",
         verdict="**confirmed**"),
    dict(key="mallen2023", authors="Mallen, A., Asai, A., Zhong, V., et al.", year="2023",
         title="When Not to Trust Language Models: Investigating Effectiveness of Parametric and "
               "Non-Parametric Memories",
         venue="ACL 2023", id="arXiv:2212.10511", role="claim tested",
         tested="reproduced as the tug-of-war: 15 repairs on the hardest, 35 regressions on the easiest",
         verdict="**confirmed**"),
    dict(key="cuconasu2024", authors="Cuconasu, F., Trappolini, G., Siciliano, F., et al.",
         year="2024", title="The Power of Noise: Redefining Retrieval for RAG Systems",
         venue="SIGIR 2024", id="arXiv:2401.14887", role="claim tested",
         tested="the mechanism behind the MedQuAD null", verdict="**confirmed**"),
    dict(key="shi2023", authors="Shi, F., Chen, X., Misra, K., et al.", year="2023",
         title="Large Language Models Can Be Easily Distracted by Irrelevant Context",
         venue="ICML 2023", id="arXiv:2302.00093", role="claim tested",
         tested="35 of 39 regressions landed on questions already answered correctly",
         verdict="**confirmed**"),
    dict(key="liu2024lost", authors="Liu, N. F., Lin, K., Hewitt, J., et al.", year="2024",
         title="Lost in the Middle: How Language Models Use Long Contexts", venue="TACL 2024",
         id="arXiv:2307.03172", role="claim applied",
         tested="centring the window on the matched chunk: +0.071 coverage for 7% more prompt",
         verdict="**confirmed**"),
    dict(key="kadavath2022", authors="Kadavath, S., Conerly, T., Askell, A., et al.", year="2022",
         title="Language Models (Mostly) Know What They Know", venue="preprint",
         id="arXiv:2207.05221", role="claim tested",
         tested="no cheap uncertainty signal correlated with failure at 3B",
         verdict="**confirmed** (scale-dependent, as predicted)"),
    dict(key="xiong2024", authors="Xiong, M., Hu, Z., Lu, X., et al.", year="2024",
         title="Can LLMs Express Their Uncertainty? An Empirical Evaluation of Confidence "
               "Elicitation in LLMs",
         venue="ICLR 2024", id="arXiv:2306.13063", role="claim tested",
         tested="verbalised self-assessment was uninformative at 3B", verdict="**confirmed**"),
    dict(key="shinn2023", authors="Shinn, N., Cassano, F., Berman, E., et al.", year="2023",
         title="Reflexion: Language Agents with Verbal Reinforcement Learning", venue="NeurIPS 2023",
         id="arXiv:2303.11366", role="method applied",
         tested="its lesson applied — grounding kept in every refinement round", verdict="applied"),
    dict(key="xiao2023", authors="Xiao, S., Liu, Z., Zhang, P., Muennighoff, N.", year="2023",
         title="C-Pack: Packed Resources For General Chinese Embeddings (BGE)", venue="preprint",
         id="arXiv:2309.07597", role="component",
         tested="won the offline retriever ladder at 0.665 hit@3", verdict="used"),
    dict(key="es2023", authors="Es, S., James, J., Espinosa-Anke, L., Schockaert, S.", year="2023",
         title="RAGAS: Automated Evaluation of Retrieval Augmented Generation", venue="preprint",
         id="arXiv:2309.15217", role="metric",
         tested="used as a diagnostic only; unusable here at a 61% null rate",
         verdict="used, with a caveat"),
    dict(key="luo2023", authors="Luo, Y., Yang, Z., Meng, F., et al.", year="2023",
         title="An Empirical Study of Catastrophic Forgetting in LLMs During Continual Fine-tuning",
         venue="preprint", id="arXiv:2308.08747", role="claim tested",
         tested="the mechanism behind the −0.292", verdict="**confirmed**"),
    dict(key="ouyang2022", authors="Ouyang, L., Wu, J., Jiang, X., et al.", year="2022",
         title="Training Language Models to Follow Instructions with Human Feedback",
         venue="NeurIPS 2022", id="arXiv:2203.02155", role="concept",
         tested="the alignment-tax framing for the fine-tuning result", verdict="applied"),
    dict(key="chen2021", authors="Chen, M., Tworek, J., Jun, H., et al.", year="2021",
         title="Evaluating Large Language Models Trained on Code (pass@k)", venue="preprint",
         id="arXiv:2107.03374", role="metric",
         tested="grounding traded diversity for consistency; pass@5 fell 0.89 → 0.74",
         verdict="used"),
    dict(key="wang2023", authors="Wang, X., Wei, J., Schuurmans, D., et al.", year="2023",
         title="Self-Consistency Improves Chain of Thought Reasoning in Language Models",
         venue="ICLR 2023", id="arXiv:2203.11171", role="concept",
         tested="diversity as the source of multi-sample gains, and what grounding spends",
         verdict="applied"),
    dict(key="geifman2017", authors="Geifman, Y., El-Yaniv, R.", year="2017",
         title="Selective Classification for Deep Neural Networks", venue="NeurIPS 2017",
         id="arXiv:1705.08500", role="framework",
         tested="the reliable@k framing — dependable correctness with abstention", verdict="applied"),
    dict(key="kamath2020", authors="Kamath, A., Jia, R., Liang, P.", year="2020",
         title="Selective Question Answering under Domain Shift", venue="ACL 2020",
         id="ACL Anthology 2020.acl-main.503", role="framework",
         tested="the selective-QA instance of the same framing", verdict="applied"),
    dict(key="benabacha2019", authors="Ben Abacha, A., Demner-Fushman, D.", year="2019",
         title="A Question-Entailment Approach to Question Answering (MedQuAD)",
         venue="BMC Bioinformatics 20(1):511", id="doi:10.1186/s12859-019-3119-4", role="dataset",
         tested="testbed 1 — 12,428 pairs in, 10,024 after cleaning; CC BY 4.0", verdict="used"),
    dict(key="cohen2025", authors="Cohen, D., Shalom, A., et al.", year="2025",
         title="WixQA: A Multi-Dataset Benchmark for Enterprise Retrieval-Augmented Generation",
         venue="preprint", id="arXiv:2505.08643", role="dataset",
         tested="testbed 2 — 200 expert questions over 6,221 help-centre articles; MIT",
         verdict="used"),
    dict(key="lee2022", authors="Lee, K., Ippolito, D., Nystrom, A., et al.", year="2022",
         title="Deduplicating Training Data Makes Language Models Better", venue="ACL 2022",
         id="arXiv:2107.06499", role="method",
         tested="the near-duplicate threshold in the cleaning rubric and the corpus scrub",
         verdict="applied"),
    dict(key="liu2024deita", authors="Liu, W., Zeng, W., He, K., et al.", year="2024",
         title="What Makes Good Data for Alignment? A Comprehensive Study of Automatic Data "
               "Selection in Instruction Tuning (DEITA)",
         venue="ICLR 2024", id="arXiv:2312.15685", role="method",
         tested="the complexity/quality/diversity axes of the readiness rubric", verdict="applied"),
    dict(key="wilson1927", authors="Wilson, E. B.", year="1927",
         title="Probable Inference, the Law of Succession, and Statistical Inference",
         venue="JASA 22(158):209-212", id="doi:10.2307/2276774", role="statistics",
         tested="every per-arm interval in this report", verdict="applied"),
    dict(key="mcnemar1947", authors="McNemar, Q.", year="1947",
         title="Note on the Sampling Error of the Difference Between Correlated Proportions or "
               "Percentages",
         venue="Psychometrika 12(2):153-157", id="doi:10.1007/BF02295996", role="statistics",
         tested="the paired significance test on every difference", verdict="applied"),
    dict(key="efron1993", authors="Efron, B., Tibshirani, R. J.", year="1993",
         title="An Introduction to the Bootstrap", venue="Chapman & Hall",
         id="ISBN 978-0412042317", role="statistics",
         tested="the paired cluster bootstrap over questions, 10,000 resamples", verdict="applied"),
    dict(key="rougier2014", authors="Rougier, N. P., Droettboom, M., Bourne, P. E.", year="2014",
         title="Ten Simple Rules for Better Figures", venue="PLOS Computational Biology 10(9)",
         id="doi:10.1371/journal.pcbi.1003833", role="presentation",
         tested="message-first design and self-contained captions in every figure here",
         verdict="applied"),
    dict(key="cleveland1984", authors="Cleveland, W. S., McGill, R.", year="1984",
         title="Graphical Perception: Theory, Experimentation, and Application to the Development "
               "of Graphical Methods",
         venue="JASA 79(387):531-554", id="doi:10.2307/2288400", role="presentation",
         tested="why differences are drawn as position on a common scale, never as bars",
         verdict="applied"),
    dict(key="appelbaum2018", authors="Appelbaum, M., Cooper, H., Kline, R. B., et al.", year="2018",
         title="Journal Article Reporting Standards for Quantitative Research in Psychology: The APA "
               "Publications and Communications Board Task Force Report",
         venue="American Psychologist 73(1):3-25", id="doi:10.1037/amp0000191", role="reporting",
         tested="the section structure of the report, the primary/secondary/exploratory grouping of "
                "its questions, and the requirement to state registration status plainly",
         verdict="applied"),
    dict(key="pineau2021", authors="Pineau, J., Vincent-Lamarre, P., Sinha, K., et al.", year="2021",
         title="Improving Reproducibility in Machine Learning Research (A Report from the NeurIPS "
               "2019 Reproducibility Program)",
         venue="JMLR 22(164):1-20", id="arXiv:2003.12206", role="reporting",
         tested="seeds and resampling counts, compute and cost, and an artifact index — all reported "
                "rather than assumed",
         verdict="applied"),
    dict(key="eliasziw1991", authors="Eliasziw, M., Donner, A.", year="1991",
         title="Application of the McNemar Test to Non-Independent Matched Pair Data",
         venue="Statistics in Medicine 10(12):1981-1991", id="doi:10.1002/sim.4780101211",
         role="statistics",
         tested="named as the correction the p-values here do not apply — the pairs are clustered "
                "by question, so the McNemar p-values are anti-conservative and the bootstrap "
                "interval is the primary statistic",
         verdict="cited as a stated limitation, not applied"),
    dict(key="icmje2023", authors="International Committee of Medical Journal Editors", year="2023",
         title="Recommendations for the Conduct, Reporting, Editing, and Publication of Scholarly "
               "Work in Medical Journals",
         venue="ICMJE (§II.A.4, artificial intelligence)",
         id="https://www.icmje.org/recommendations/", role="reporting",
         tested="the form of the AI-tooling disclosure in §14.2 — which content, which action, "
                "which oversight, rather than a bare acknowledgement",
         verdict="applied"),
    dict(key="brand2015", authors="Brand, A., Allen, L., Altman, M., Hlava, M., Scott, J.",
         year="2015",
         title="Beyond Authorship: Attribution, Contribution, Collaboration, and Credit",
         venue="Learned Publishing 28(2):151-155", id="doi:10.1087/20150211", role="reporting",
         tested="the CRediT roles claimed in §14.1, stated for a single author so that "
                "responsibility for the errors in §11 is unambiguous",
         verdict="applied"),
]


def literature() -> List[Dict[str, str]]:
    """The works this project used or tested, with full citations.

    Kept as structured records in one place so the comparison table and the
    report's reference list cannot disagree about what was cited or how it
    turned out. A test asserts every work named in the report appears here.
    """
    return [dict(entry) for entry in LITERATURE]


def project_timeline() -> List[Dict[str, str]]:
    """The real order of work, dated from evidence rather than from memory.

    Worth generating rather than asserting, because the intuitive order is
    wrong in a way that flatters the early work. It is natural to narrate
    "collect data → clean it → run experiments", and every account of this
    project drifts toward that shape. The dates say otherwise: the original
    experiments ran in **November 2025** on an unidentified medical Q&A dump
    with no held-out split, and the dataset was only identified, licensed,
    cleaned and split in **July 2026** — two days *after* the audit that found
    the original results invalid.

    That ordering is not a detail. Putting the cleaning first implies the early
    results were measured on a clean, properly split dataset. They were not,
    and that absence is one of the reasons they did not survive.
    """
    events: List[Dict[str, str]] = []
    for phase in ("phase0", "phase1", "phase2", "phase3", "phase4", "phase5", "phase6"):
        path = LOGS / phase / "summary.jsonl"
        if not path.is_file():
            continue
        records = _read_jsonl(path)
        stamps = sorted(r.get("timestamp", "") for r in records if r.get("timestamp"))
        if stamps:
            events.append(
                {
                    "date": stamps[0][:10],
                    "what": f"the original experiments, {phase}",
                    "kind": "run",
                    "source": _rel(path),
                }
            )
    # The rebuilt studies, dated from their own run summaries. WixQA is
    # deliberately absent: neither its records nor its manifest carry a
    # timestamp, so it can only be placed by the decision that reports it, and
    # inventing a date from a file's modification time would be a guess
    # dressed as evidence.
    for study, label in (
        ("teaching-loop-medquad", "the loop ablation"),
        ("rag-medquad", "retrieval on a domain the model knows"),
        ("rag-medquad-reliability", "the reliability probe"),
        ("rag-medquad-fair-tests", "the three rescue attempts for the retrieval null"),
        ("student-prompt-medquad", "the student-prompt comparison"),
    ):
        stamps = []
        try:
            for runs in study_runs(study).values():
                stamps.extend(r.summary.get("timestamp", "") for r in runs)
        except MissingEvidence:
            continue
        stamps = sorted(s for s in stamps if s)
        if stamps:
            events.append(
                {
                    "date": stamps[0][:10],
                    "what": f"the rebuilt experiments — {label}"
                    + (f", through {stamps[-1][:10]}" if stamps[-1][:10] != stamps[0][:10] else ""),
                    "kind": "run",
                    "source": f"runs/{study}",
                }
            )

    for entry in decision_log():
        events.append(
            {
                "date": entry["date"],
                "what": f"{entry['id']} — {entry['title']}",
                "kind": "decision",
                "source": ".claude/rules/decisions.md",
            }
        )
    return sorted(events, key=lambda e: (e["date"], e["kind"] == "decision", e["what"]))


def decision_log() -> List[Dict[str, str]]:
    """Every architecture decision, parsed from the decision log.

    The record of *why*, which is the half a results table cannot carry. Parsed
    rather than retyped so a decision cannot exist in a report without existing
    in the log that governs the project.
    """
    path = ROOT / ".claude" / "rules" / "decisions.md"
    if not path.is_file():
        raise MissingEvidence(f"missing decision log: {path}")
    header = re.compile(r"^## (ADR-\d+) — (.+?) \((\d{4}-\d{2}-\d{2})\) · (.+)$", re.MULTILINE)
    entries: List[Dict[str, str]] = []
    text = path.read_text(encoding="utf-8")
    matches = list(header.finditer(text))
    for i, m in enumerate(matches):
        body = text[m.end(): matches[i + 1].start() if i + 1 < len(matches) else len(text)]
        context = re.search(r"\*\*Context:\*\*\s*(.+?)(?=\n\*\*|\Z)", body, re.DOTALL)
        entries.append(
            {
                "id": m.group(1),
                "title": m.group(2).strip(),
                "date": m.group(3),
                "status": m.group(4).strip(),
                "why": " ".join((context.group(1) if context else "").split())[:300],
            }
        )
    if not entries:
        raise MissingEvidence("decision log parsed to zero entries -- the header format changed")
    return sorted(entries, key=lambda e: e["id"])


def v1_cost_estimate() -> Dict[str, Any]:
    """What the retired project actually spent, at its own quoted rates.

    The rates come from the deleted notebook (recovered to
    `docs/archive/v1-notebook-narrative.md`); the token counts come from the
    logs. The two cannot be combined exactly: the runs recorded student and
    teacher totals but never split input from output, and the two are priced
    differently. So this returns a bounded range -- all-input to all-output --
    rather than a single figure that would imply a precision the logs do not
    support.
    """
    rates = {  # USD per 1M tokens, as quoted by the original project
        "teacher (Llama 3.3 70B)": {"input": 0.59, "output": 0.79},
        "student/judge (Llama 3.1 8B)": {"input": 0.05, "output": 0.08},
    }
    usd_to_aud = 1.53
    student = teacher = 0
    for phase in ("phase0", "phase1", "phase2", "phase3", "phase4", "phase5", "phase6"):
        for record in v1_phase_summaries(phase):
            student += int(record.get("student_tokens_total") or 0)
            teacher += int(record.get("teacher_tokens_total") or 0)
    low = (teacher * rates["teacher (Llama 3.3 70B)"]["input"]
           + student * rates["student/judge (Llama 3.1 8B)"]["input"]) / 1e6
    high = (teacher * rates["teacher (Llama 3.3 70B)"]["output"]
            + student * rates["student/judge (Llama 3.1 8B)"]["output"]) / 1e6
    return {
        "student_tokens": student,
        "teacher_tokens": teacher,
        "usd_low": low,
        "usd_high": high,
        "aud_low": low * usd_to_aud,
        "aud_high": high * usd_to_aud,
        "rates": rates,
        "usd_to_aud": usd_to_aud,
    }


def v1_pass_threshold_sweep() -> List[Tuple[float, float, int]]:
    """(pass threshold, mean pass rate, runs) from the old hyper-parameter grid.

    The sharpest thing in the retired work, and the one table in it that
    reconciles against its own logs exactly. The old system's "pass rate" was
    a composite score compared against a threshold the experimenter chose, and
    the grid shows what that choice was worth: 0.975 at the loosest setting,
    0.337 at the strictest. 0.80 was selected, and the headline 25% -> 83% was
    then reported as a measurement.

    It is the exact mirror of the decision made in the rebuild, where the bar
    was moved the other way -- upward, until the baseline stopped passing
    everything -- and the two belong on one page.
    """
    grouped: Dict[float, List[float]] = {}
    for record in v1_phase_summaries("phase3"):
        threshold = record.get("config_used", {}).get("pass_threshold")
        rate = record.get("pass_rate")
        if threshold is not None and rate is not None:
            grouped.setdefault(float(threshold), []).append(float(rate))
    return [
        (threshold, sum(rates) / len(rates), len(rates))
        for threshold, rates in sorted(grouped.items())
    ]


def v1_feedback_styles() -> List[Tuple[str, float]]:
    """The teacher-style comparison the old work used to pick its prompt.

    Worth keeping because the rebuild later overturned it: this run made ORCA
    the house style, and a properly-powered re-test found it indistinguishable
    from a minimal prompt. A project falsifying its own earlier conclusion with
    its own data is the record working as intended.
    """
    styles = {"P2A": "principle", "P2B": "chain-of-thought", "P2C": "ORCA"}
    out: List[Tuple[str, float]] = []
    for record in v1_phase_summaries("phase2"):
        key = record.get("experiment_id", "")[:3]
        if key in styles and record.get("pass_rate") is not None:
            out.append((styles[key], float(record["pass_rate"])))
    return sorted(out, key=lambda r: -r[1])


def v1_warmup() -> Dict[str, Any]:
    """The first phase: does the loop run end to end at all."""
    records = v1_phase_summaries("phase0")
    if not records:
        raise MissingEvidence("no phase0 summary")
    first = records[0]
    return {
        "pass_rate": first.get("pass_rate"),
        "questions": first.get("num_questions"),
        "memory_hits": first.get("memory_hits"),
        "avg_rounds": first.get("avg_rounds"),
        "semantic_similarity": first.get("semantic_similarity"),
    }


def v1_claim_vs_log() -> List[Dict[str, Any]]:
    """The retraction table's rows: what the write-up claimed, what the log
    holds, and how the two differ.

    Every `logged` value below is read live from `logs/experiments/`; the
    `claimed` values are quoted from the archived document, which carries a
    SUPERSEDED banner. Where a claim has no log at all, that is stated --
    an unsourced number is a different (and worse) failure than an inflated
    one, and the distinction belongs in the record.
    """
    rows: List[Dict[str, Any]] = []

    p5 = {r.get("experiment_id", ""): r for r in v1_phase_summaries("phase5")}
    baseline = next((r for k, r in p5.items() if "Baseline" in k), {})
    optimized = next((r for k, r in p5.items() if "Optimi" in k), {})
    rows.append(
        {
            "claim": "pass rate 25% -> 83%",
            "logged": f"{baseline.get('pass_rate', float('nan')):.2f} -> "
            f"{optimized.get('pass_rate', float('nan')):.2f}",
            "verdict": "inflated at both ends; the real logged gain is +51pt, not +58",
            "source": _rel(LOGS / "phase5" / "summary.jsonl"),
        }
    )

    p6 = v1_phase_summaries("phase6")
    same_q = next((r for r in p6 if "Same" in r.get("experiment_id", "")), {})
    rows.append(
        {
            "claim": "ground-truth memory reaches 100% accuracy",
            "logged": f"pass_rate {same_q.get('pass_rate')} at "
            f"memory_hit_rate {same_q.get('memory_hit_rate')}",
            "verdict": "the number is real; it measures the store returning its own "
            "answer key on every question",
            "source": _rel(LOGS / "phase6" / "summary.jsonl"),
        }
    )

    phases = v1_phase_table()
    logged_tokens = sum(p["tokens"] for p in phases)
    rows.append(
        {
            "claim": "the whole project consumed 920,814 tokens, about $0.50 AUD",
            "logged": f"{logged_tokens:,} tokens across all {len(phases)} phases",
            "verdict": f"understated {logged_tokens / 920_814:.1f}x — the per-phase figures quoted "
            "one run each where a phase had two, three, or twelve",
            "source": _rel(LOGS),
        }
    )

    warmup = v1_warmup()
    rows.append(
        {
            "claim": "the warm-up phase ran on 20 questions, 2.7 rounds each",
            "logged": f"{warmup['questions']} questions, {warmup['avg_rounds']} rounds "
            f"(pass rate {warmup['pass_rate']} matches)",
            "verdict": "the headline rate is right; the setup around it is not, and the same "
            "document contradicts itself on the count elsewhere",
            "source": _rel(LOGS / "phase0" / "summary.jsonl"),
        }
    )

    styles = dict(v1_feedback_styles())
    rows.append(
        {
            "claim": "teacher styles scored ORCA 90%, principle 85%, chain-of-thought 80%",
            "logged": ", ".join(f"{name} {rate:.0%}" for name, rate in v1_feedback_styles()),
            "verdict": "ORCA's number is right, the two it beat are overstated by 35-40 points — "
            "and a properly powered re-test later found ORCA indistinguishable from a minimal "
            "prompt (p=0.58), so the conclusion this table was used to justify does not hold either",
            "source": _rel(LOGS / "phase2" / "summary.jsonl"),
        }
    )

    p1 = {r.get("experiment_id", ""): r.get("pass_rate") for r in v1_phase_summaries("phase1")}
    with_mem = next((v for k, v in p1.items() if "WithMemory" in k), None)
    no_mem = next((v for k, v in p1.items() if "NoMemory" in k), None)
    rows.append(
        {
            "claim": "memory beats no-memory by +5.0 points",
            "logged": f"with-memory {with_mem} vs no-memory {no_mem}",
            "verdict": "sign reversed -- the logged runs show memory doing worse",
            "source": _rel(LOGS / "phase1" / "summary.jsonl"),
        }
    )

    phase3 = v1_phase_summaries("phase3")
    temps = sorted({r.get("config_used", {}).get("student_temp") for r in phase3} - {None})
    rows.append(
        {
            "claim": "student temperature 0.0 / 0.3 / 0.5 compared; 0.0 is critical",
            "logged": f"only {' and '.join(str(t) for t in temps)} were run "
            f"({len(phase3)} configs, not the 27 a three-level grid implies)",
            "verdict": "two of the three compared settings have no run behind them",
            "source": _rel(LOGS / "phase3" / "summary.jsonl"),
        }
    )

    p4 = {
        r.get("config_used", {}).get("domain", r.get("experiment_id", "?")): r.get("pass_rate")
        for r in v1_phase_summaries("phase4")
    }
    rows.append(
        {
            "claim": "hard domains Heart/Lung 70% and Genetic 60%",
            "logged": ", ".join(f"{k} {v}" for k, v in sorted(p4.items())),
            "verdict": "neither domain appears in the logs; every domain that ran scored >= 0.80",
            "source": _rel(LOGS / "phase4" / "summary.jsonl"),
        }
    )
    return rows

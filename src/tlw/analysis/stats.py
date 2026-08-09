"""The pre-registered statistics (teaching-loop-protocol.md §4 -- implemented exactly).

Three tools, each with one job (§4.2):

- `wilson_interval`       -- descriptive, single-proportion 95% CI per arm.
- `paired_cluster_bootstrap` -- the HEADLINE: resample QUESTIONS (the
  cluster) with replacement, seeds pooled inside each cluster, recompute
  pass_rate(arm_a) - pass_rate(arm_b) per resample, 95% CI = the 2.5/97.5
  percentiles over >=10,000 resamples. Deterministic given `seed`.
- `exact_mcnemar`         -- companion significance on the discordant pairs.

Nothing here reads a run artifact directly (that is `loaders.py`); these
functions take plain aggregated inputs so they are unit-testable against
hand-computable synthetic examples (T2.8 build instruction 5).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

Z_975 = 1.959963984540054  # scipy.stats.norm.ppf(0.975), hardcoded so this
# module has no scipy dependency (stdlib+numpy only per T2.8 build rule 6).


@dataclass(frozen=True)
class WilsonInterval:
    """Descriptive per-arm interval (teaching-loop-protocol §4.2 "secondary/descriptive")."""

    k: int
    n: int
    point: float
    low: float
    high: float
    z: float = Z_975


def wilson_interval(k: int, n: int, z: float = Z_975) -> WilsonInterval:
    """Wilson score interval for a single proportion k/n. Behaves well at
    small n and near 0/1 (teaching-loop-protocol §4.2), unlike a naive normal-approx CI.

    n=0 -> point/low/high all 0.0 (an empty arm has no defensible interval;
    callers must treat n=0 as "no data", not "0% pass rate").
    """
    if n < 0 or k < 0 or k > n:
        raise ValueError(f"invalid (k={k}, n={n}) for a proportion")
    if n == 0:
        return WilsonInterval(k=0, n=0, point=0.0, low=0.0, high=0.0, z=z)

    p_hat = k / n
    denom = 1.0 + z * z / n
    center = (p_hat + z * z / (2 * n)) / denom
    half_width = (z * math.sqrt(p_hat * (1 - p_hat) / n + z * z / (4 * n * n))) / denom
    low = max(0.0, center - half_width)
    high = min(1.0, center + half_width)
    return WilsonInterval(k=k, n=n, point=p_hat, low=low, high=high, z=z)


@dataclass(frozen=True)
class BootstrapResult:
    """The headline C-B (or any arm-pair) delta with its paired
    cluster-bootstrap 95% CI (teaching-loop-protocol §4.2/§4.3)."""

    arm_a: str
    arm_b: str
    point_estimate: float  # pass_rate(arm_a) - pass_rate(arm_b), all replicates pooled
    ci_low: float
    ci_high: float
    n_clusters: int  # number of held-out questions with data in BOTH arms
    n_resamples: int
    seed: int

    def crosses_zero(self) -> bool:
        return self.ci_low <= 0.0 <= self.ci_high

    def summary_line(self) -> str:
        sig = "NO SIGNIFICANT EFFECT (CI crosses 0)" if self.crosses_zero() else "CI excludes 0"
        return (
            f"{self.arm_a}-{self.arm_b}: {self.point_estimate:+.3f} "
            f"[{self.ci_low:+.3f}, {self.ci_high:+.3f}] (95% paired cluster bootstrap, "
            f"n_clusters={self.n_clusters}, resamples={self.n_resamples}) -- {sig}"
        )


def paired_cluster_bootstrap(
    cluster_table: Dict[str, Dict[str, List[bool]]],
    arm_a: str,
    arm_b: str,
    n_resamples: int = 10_000,
    seed: int = 0,
) -> BootstrapResult:
    """Paired cluster bootstrap over questions (teaching-loop-protocol §4.2 "Primary").

    `cluster_table`: {question_id: {arm: [passed_bool, ...]}} -- the list
    per arm holds one entry per seed replicate for that question (seeds
    pooled *inside* the cluster, per §4.2 "Across seeds"). Only questions
    that have at least one replicate for BOTH `arm_a` and `arm_b` are
    used as clusters (paired design) -- an unpaired question would let an
    arm with more/less coverage bias the delta.

    Deterministic: same `cluster_table`/`seed`/`n_resamples` -> identical
    output (numpy Generator, PCG64, seeded -- §0.3).

    **Clusters are ordered by `str(question_id)`, and that is load-bearing.**
    The generator draws cluster *indices*, so the order the ids are laid out in
    decides which questions each resample picks. Two callers that keyed the same
    questions as `"12"` and as `12` therefore sorted them differently -- lexical
    versus numeric -- and produced confidence intervals differing in the third
    decimal from identical data and an identical seed. The point estimate never
    moved, because it does not depend on order; only the interval did, which is
    the harder failure to notice. Normalising here fixes every caller at once and
    makes the key's *type* irrelevant, which is the property that was silently
    assumed. Neither ordering is more correct statistically; agreeing is.
    """
    qids = sorted(
        (
            q
            for q, arms in cluster_table.items()
            if arm_a in arms and arms[arm_a] and arm_b in arms and arms[arm_b]
        ),
        key=str,
    )
    n = len(qids)
    if n == 0:
        raise ValueError(
            f"paired_cluster_bootstrap({arm_a!r}, {arm_b!r}): no question has data "
            f"in both arms -- cannot pair"
        )

    pass_a = np.array([sum(cluster_table[q][arm_a]) for q in qids], dtype=np.float64)
    total_a = np.array([len(cluster_table[q][arm_a]) for q in qids], dtype=np.float64)
    pass_b = np.array([sum(cluster_table[q][arm_b]) for q in qids], dtype=np.float64)
    total_b = np.array([len(cluster_table[q][arm_b]) for q in qids], dtype=np.float64)

    point_estimate = float(pass_a.sum() / total_a.sum() - pass_b.sum() / total_b.sum())

    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n, size=(n_resamples, n))  # resample CLUSTERS with replacement

    resampled_pass_a = pass_a[idx].sum(axis=1)
    resampled_total_a = total_a[idx].sum(axis=1)
    resampled_pass_b = pass_b[idx].sum(axis=1)
    resampled_total_b = total_b[idx].sum(axis=1)

    rate_a = resampled_pass_a / resampled_total_a
    rate_b = resampled_pass_b / resampled_total_b
    deltas = rate_a - rate_b

    ci_low, ci_high = np.percentile(deltas, [2.5, 97.5])

    return BootstrapResult(
        arm_a=arm_a,
        arm_b=arm_b,
        point_estimate=point_estimate,
        ci_low=float(ci_low),
        ci_high=float(ci_high),
        n_clusters=n,
        n_resamples=n_resamples,
        seed=seed,
    )


@dataclass(frozen=True)
class McNemarResult:
    """Companion paired-significance test (teaching-loop-protocol §4.2 "Companion
    significance"). `b` = arm_a PASS / arm_b FAIL, `c` = arm_a FAIL / arm_b
    PASS (discordant pairs); concordant pairs (both pass or both fail)
    carry no information for McNemar and are excluded, per the standard
    test definition."""

    arm_a: str
    arm_b: str
    b: int
    c: int
    n_pairs: int  # total paired observations considered (concordant + discordant)
    p_value: float


def exact_mcnemar(pairs: Sequence[Tuple[bool, bool]], arm_a: str = "a", arm_b: str = "b") -> McNemarResult:
    """Exact (binomial) McNemar test on paired PASS/FAIL observations.

    `pairs`: sequence of (passed_a, passed_b) for the SAME observation unit
    (one question, one seed replicate -- teaching-loop-protocol §4.2 names the unit as
    "B-vs-C discordant pairs"; when seeds are pooled, each (question, seed)
    replicate is treated as one paired observation here, which is the
    simplest generalization -- flagged under NOT DONE in the report for
    T2.8, since replicates from the same question are not strictly
    independent).

    Exact two-sided p-value: `2 * min(P(X<=min(b,c)), P(X>=max(b,c)))`
    under `X ~ Binomial(b+c, 0.5)`, capped at 1.0 -- the standard exact
    McNemar formulation (no continuity correction, no chi-square
    approximation, so it is valid at the small counts this eval expects).
    """
    b = sum(1 for pa, pb in pairs if pa and not pb)
    c = sum(1 for pa, pb in pairs if (not pa) and pb)
    n_pairs = len(pairs)

    if b + c == 0:
        # No discordant pairs at all -- the two arms agree on every paired
        # observation. Not significant by construction; p=1.0 is the
        # correct, honest value (nothing to reject).
        return McNemarResult(arm_a=arm_a, arm_b=arm_b, b=b, c=c, n_pairs=n_pairs, p_value=1.0)

    n = b + c
    k = min(b, c)
    p_le = sum(math.comb(n, i) for i in range(0, k + 1)) / (2**n)
    p_value = min(1.0, 2 * p_le)

    return McNemarResult(arm_a=arm_a, arm_b=arm_b, b=b, c=c, n_pairs=n_pairs, p_value=p_value)


def per_seed_deltas(
    cluster_table: Dict[str, Dict[str, List[bool]]],
    arm_a: str,
    arm_b: str,
    seeds: Sequence[int],
    seed_index: Dict[str, Dict[str, List[int]]],
) -> Dict[int, float]:
    """Mean +/- spread of C-B across the individual seeds (teaching-loop-protocol §4.2
    "also report mean +/- spread ... as a robustness check"). `seed_index`
    mirrors `cluster_table`'s shape but holds the seed id for each replicate
    (same list order) so a replicate can be attributed back to its seed.

    Returns {seed: pass_rate(arm_a, seed) - pass_rate(arm_b, seed)} for
    every seed that has data for both arms; a seed with no paired data is
    silently omitted (report.py surfaces the omission count).
    """
    out: Dict[int, float] = {}
    for s in seeds:
        pass_a = total_a = pass_b = total_b = 0
        for q, arms in cluster_table.items():
            if arm_a not in arms or arm_b not in arms:
                continue
            idx_a = seed_index.get(q, {}).get(arm_a, [])
            idx_b = seed_index.get(q, {}).get(arm_b, [])
            for val, sd in zip(arms[arm_a], idx_a):
                if sd == s:
                    total_a += 1
                    pass_a += int(val)
            for val, sd in zip(arms[arm_b], idx_b):
                if sd == s:
                    total_b += 1
                    pass_b += int(val)
        if total_a > 0 and total_b > 0:
            out[s] = (pass_a / total_a) - (pass_b / total_b)
    return out

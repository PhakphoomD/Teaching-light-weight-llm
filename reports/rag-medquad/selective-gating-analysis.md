# Selective retrieval — can the model be told when to retrieve?

> **Note, 2026-08-09.** Two things a reader should know before using the table in §2.
>
> **The 70B row was never completed.** It is still marked *pending Groq reset* below, and it stayed
> that way — the daily token cap was never free at the right moment and the question was overtaken.
> It is left visible rather than deleted, because a blank row is the honest record of a test that
> was planned and not run.
>
> **The conclusion it points at was reached anyway, by a different route.** A later study asked the
> same question of a different intervention — whether the model can tell when its *own answer* needs
> another pass — and got the same shape of answer: an oracle gate would gain 0.038, a gate driven by
> the model's own self-assessment gained 0.000, and the 3B called its answer complete 59% of the time
> including when it was wrong. Two independent replications now say the missing component is a
> reliable gate, not a better intervention.
>
> The rest of this document is as it was written on 2026-07-16.

**Status:** design + offline evidence (2026-07-16) · **Owner:** program-architect + qa
**Premise (ADR-027):** always-on RAG is a **net wash** on the 3B (−0.005) — a tug-of-war that
fixes ~38% of knowledge-gap questions but breaks a similar number of easy ones via distraction.
The goal of selective RAG: **ground only when it helps**, keeping the hard-question gains without
the easy-question tax.

---

## 1. The prize is real — the oracle upper bound

Computed from the existing runs (`runs_rag/`, 125×3): if a gate could ground **only** the
questions the baseline fails (the 17.9% knowledge-gap set) and leave the rest ungrounded:

| Configuration | Pass-rate | vs baseline |
|---|---|---|
| 3B baseline | 0.821 | — |
| 3B+RAG (always-on) | 0.816 | **−0.005** (the null) |
| **3B + ORACLE-selective RAG** | **0.920** | **+0.099** |

So the *retrieval + knowledge* is sufficient for a **+9.9-point** gain — **the entire bottleneck
is the gate** (deciding *when* to ground). Selective RAG is worth building *iff* a real gate can
approximate this oracle.

---

## 2. What does NOT work as a gate (offline-validated, so we don't build it)

A gate must predict, at inference, "will the baseline fail this question?" (≈ is there a knowledge
gap?). Cheap signals were tested against the known baseline pass/fail on all 375 runs — **all fail**:

| Candidate gate signal | Result | Why it fails |
|---|---|---|
| **Answer length** (short = uncertain) | precision ~0.35 at any threshold | failed answers are only slightly shorter (median 144 vs 175 words) |
| **Hedging words** ("may", "consult", …) | no separation (1.82 vs 2.14 /ans) | failures aren't more hedged |
| **Self-consistency** (agreement across 3 seed samples) | corr with failure = **+0.02**, non-monotonic | the 3B is often **confidently wrong** — a stable misconception has HIGH agreement yet FAILS (high-agree tercile fails *more*: 0.236 vs mid 0.119) |

**Conclusion:** model-uncertainty gates don't work here — the 3B doesn't "know what it doesn't
know" on this domain. A gate based on the model's own confidence is a dead end.

---

## 3. What might work — verify-then-ground (retrieval-adds-knowledge gate)

Gate on **whether the retrieved passages actually add/correct knowledge**, not on model confidence:

1. Generate an **ungrounded draft** D (= baseline behaviour).
2. Retrieve passages P for the question.
3. **Gate call:** "Given DRAFT D and PASSAGES P, do the passages contain important factual
   information that is MISSING from or CONTRADICTS the draft? YES/NO." (§0.2-safe — no gold answer;
   compares draft to non-gold TRAIN passages only.)
4. If **YES** → regenerate grounded on P. If **NO** → keep D.

**Why this could beat the oracle-less always-on:** on an *easy* question the draft is already
complete, so even a tangential passage adds nothing new → gate says NO → keep the correct draft
(no distraction). On a *hard* question the draft has a gap a relevant passage fills → gate says
YES → ground → recover. It targets the *knowledge-add*, which is exactly what separates the two
regimes — unlike model-uncertainty, which doesn't.

**Cost:** +1 short gate call per question, +1 grounded regen only on the ~gate-fires subset.

**Risk:** the gate is itself an LLM judgment; a weak gate (3B) may mis-detect "adds knowledge".
A stronger gate model (Groq 8b/70B) is an option since the gate is not the student.

---

## 4. Cheap offline test BEFORE building the arm (no student re-runs)

We already have, per (question, seed): the baseline draft + its pass/fail AND the always-on-RAG
answer + its pass/fail. So we can **simulate** verify-then-ground without re-running the student:

- run only the **gate call** per (question, seed) [draft = the logged baseline answer; passages =
  retrieved now];
- **selective outcome** = if gate=YES use the logged RAG answer's pass/fail, else the baseline's;
- compare selective pass-rate to baseline (0.821), always-on (0.816), oracle (0.920).

If selective ≫ baseline → the gate works → build it as a real arm. If selective ≈ baseline/always-on
→ the gate is too weak → try a stronger gate model or a better retriever (aspect-aware re-rank),
or report that cheap selective RAG is not reachable on this testbed (an honest negative, like §2).
`scripts/rag/selective_simulation.py` implements this simulation (gate model configurable).

### Results so far (2026-07-16/17)

| Gate | Fired on | Selective pass-rate | vs baseline |
|---|---|---|---|
| oracle (cheats — uses the label) | 17.9% | **0.920** | **+0.099** |
| local `llama3.1:8b`, lenient prompt | **99%** | 0.819 | −0.003 (≈ always-on) |
| local `llama3.1:8b`, strict prompt | **0%** | 0.821 | +0.000 (≈ baseline) |
| Groq `llama-3.3-70b`, strict prompt | *pending Groq reset* | — | — |

**The 8B gate is bimodal-useless** — it follows the prompt's *tone* wholesale (99% fire on a lenient
prompt, 0% on a strict one) with no content discrimination, so it can't land in the ~18% "needs-RAG"
sweet spot. This mirrors §2: the gate decision ("is the draft inadequate / does the passage add a
missing fact?") is nearly as hard as the task itself, and an 8B can't do it. The **70B strong-reasoner
gate is the last cheap test** (`finish_when_groq_ready.py` runs it on the seed-42 subset when the cap
resets). If 70B also fails to discriminate, the honest conclusion is that selective RAG on this testbed
needs a *learned* gate or a *better retriever* (aspect-aware, §3 root-cause), not an LLM self-gate —
with the +9.9pt oracle standing as the motivating headroom (future work).

---

## 5. Architecture (only if §4 validates)

A new slot-E arm strategy **`S` (selective)** in `src/tlw/loop/strategies.py`: draft → gate → maybe
reground, reusing the `rag` MemoryBackend for retrieval and the existing leak seals (RAG-L3 on the
grounded prompt). No new memory type. Config `params.arm: S`, `memory.type: rag`. The gate model is
a slot (reuse `eval.judge` or a dedicated `gate` model). Ablation arm added to RAG_SPEC §3:
{3B, 3B+RAG, 3B+selective-RAG}, same 125×3, headline `selective − baseline` with the usual CI.

---

## 6. Anti-leak
Same seals as always-on RAG (RAG_SPEC §5): corpus is TRAIN-only (RAG-L1/L2), the gate and grounded
prompts run through `assert_gt_free` / the RAG-L3 filter, and the gate sees only (draft, passages) —
never the gold answer (§0.2). The gate is a NEW call, not the correctness judge.

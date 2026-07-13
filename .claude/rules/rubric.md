---
paths:
  - "data/**"
  - "scripts/**"
  - "tools/**"
  - "src/data/**"
---

# Dataset Readiness Rubric v0.1 (evidence-backed)

Loads when working with data/tooling. All thresholds/weights are **config values**, not hardcoded.

## 7 dimensions (0–100, bands 🟢≥ / 🟡 / 🔴<)
| # | Dimension | Compute | 🟢/🟡/🔴 | Evidence |
|---|---|---|---|---|
| D1 | Structural | valid_nonempty_pairs / total | 99/95 | data-centric (gate) |
| D2 | Cleanliness | 1 − residual_noise_rate (boilerplate/URL/`??`) | 98/90 | LIMA; Lee 2022 |
| D3 | Uniqueness | answer_clusters@cos0.90 / N | 95/85 | Lee 2022; DEITA τ=0.90 |
| D4 | Quality | independent LLM-judge per-pair mean | 75/60 | AlpaGasus; DEITA |
| D5 | Complexity | substantive / N (exclude templates) | 85/70 | DEITA Evol-Complexity |
| D6 | Diversity | norm. question-type entropy + embedding spread | 70/50 | DEITA; LIMA |
| D7 | Answerability | 0.6·relevance(Q,A) + 0.4·self_contained | 80/65 | RAGAS |

## Volume gate (caps verdict per target)
| target | 🟢 | 🟡 | 🔴 |
|---|---|---|---|
| lora | ≥1000 | 300–1000 | <300 (LIMA 1k, DEITA 6k) |
| rag  | ≥200 | 50–200 | <50 |
| eval | ≥200 heldout | 100–200 | <100 |

## Per-target weights (sum=1.0)
| Dim | rag | lora | eval |
|---|---|---|---|
| Answerability | 0.25 | 0.05 | 0.20 |
| Cleanliness | 0.20 | 0.15 | 0.10 |
| Quality | 0.15 | 0.25 | 0.15 |
| Uniqueness | 0.10 | 0.20 | 0.25 |
| Complexity | 0.05 | 0.15 | 0.20 |
| Diversity | 0.10 | 0.15 | 0.05 |
| Structural | 0.15 | 0.05 | 0.05 |

## Verdict
```
Overall = Σ weight_target × D_i
Volume 🔴  → NOT READY (cap 49)
READY      : Overall ≥ 75 AND no 🔴 AND Volume ≥ 🟡
NEEDS WORK : 50–74
NOT READY  : <50 OR Volume 🔴 OR Structural 🔴
```
Always report before-clean vs after-clean projected Overall.

## References
LIMA (arXiv:2305.11206) · DEITA (2312.15685) · AlpaGasus (survey 2402.05123) · Deduplicating Training Data (Lee et al., ACL 2022) · RAGAS · MedQuAD (Ben Abacha & Demner-Fushman 2019).

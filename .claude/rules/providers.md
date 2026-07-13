# Providers & Models (config — ADR-013)

## Groq (free tier — primary cloud). Enabled at org level:
| model | RPM | RPD | TPM | TPD | fit for |
|---|---|---|---|---|---|
| `llama-3.1-8b-instant` | 30 | 14.4K | 6K | 500K | fast/cheap small |
| `llama-3.3-70b-versatile` | 30 | 1K | 12K | 100K | teacher / Llama judge |
| `qwen/qwen3-32b` | 60 | 1K | 6K | 500K | teacher / **Qwen judge (independent of Llama)** |
| `qwen/qwen3.6-27b` | 30 | 1K | 8K | 200K | teacher / Qwen judge |
⚠️ Free tier: watch **daily** caps. 70B = only 1K req/day + 100K tok/day → batch eval carefully; prefer 8B/32B for bulk.

## Local (Ollama) — free, private, RTX 4060 8GB:
| model | size | fit for |
|---|---|---|
| `qwen2.5:7b-instruct` | 4.7GB | student **or** local judge |
| `llama3.1:8b` | 4.9GB | student (original baseline, ADR-001) |
| `qwen2.5vl:7b` / `:3b` | vision | not for text Q&A |

## §0.2 role rule — judge family ≠ student family
Avoid self-preference bias: pick student and judge from **different** families.
- student = **Llama** (llama3.1:8b) → judge = **Qwen** (Groq qwen3-32b or local qwen2.5:7b)
- student = **Qwen** (qwen2.5:7b) → judge = **Llama** (Groq llama-3.3-70b)
Teacher may be either big model; it is not the measurement.

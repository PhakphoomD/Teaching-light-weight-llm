# How to regenerate any of this from scratch

The [experiment report](../docs/EXPERIMENT_RESULTS.md) §13 lists the *analysis* commands — the ones
that recompute every published number from logs already in this repository, with no GPU, no API key
and no model run. **This file is the layer beneath that:** how the logs themselves were produced.

Nothing here needs to be run to check a number. It is here so that a reader who does not trust the
committed logs can rebuild them, and so that the operating detail the per-study reports used to
carry did not disappear when they were merged into §7.

Run Python through the project's environment, not a bare `python` (§0.5):
`C:\Users\ham25\.conda\envs\tlw\python.exe`. Set `HF_HUB_OFFLINE=1` for anything that embeds — the
sentence-transformers loader otherwise stalls for about a minute per process when it cannot reach
huggingface.co.

---

## Study 1 — the teaching loop (§7.1)

Twelve runs: four arms × three seeds. The seed is supplied by the environment, so one config file
drives all three.

```bash
# per seed in {13, 42, 123}, per arm config in
#   {1-baseline, 2-self-refine, 3-teacher-feedback, 4-teacher-sees-answer}
EXPERIMENT_PARAMS_SEED=<seed> \
  python run.py --config experiments/teaching-loop/<CONFIG>.yml \
  --data data/clean/Diabetes_and_Digestive_and_Kidney_Diseases_heldout.jsonl \
  --teacher-fallback local:qwen2.5:7b-instruct --judge-fallback local:llama3.1:8b

python -m src.tlw.analysis --runs-dir runs/teaching-loop-medquad --comparison C-B --comparison B-A
```

Arm D has two seeds rather than three: the leakage guard aborted the seed-123 run when the sighted
teacher echoed a span of the reference into its feedback. That is reported as an abort, not rerun.

## Study 2 — retrieval on a known domain (§7.2)

The index must be built before the run, and it must exclude the held-out split.

```bash
# 1. the held-out-free index (506 records in, 414 indexed after two scrubs)
HF_HUB_OFFLINE=1 python -m tools.rag.cli \
  --source  data/clean/Diabetes_and_Digestive_and_Kidney_Diseases_train.jsonl \
  --exclude data/clean/Diabetes_and_Digestive_and_Kidney_Diseases_heldout.jsonl \
  --out     indexes/medquad-diabetes-train

# 2. the treatment arm, per seed in {13, 42, 123}. The baseline is the Track-A arm-A run,
#    copied into this study as small-model-no-rag rather than re-run.
EXPERIMENT_PARAMS_SEED=<seed> HF_HUB_OFFLINE=1 \
  python run.py --config experiments/rag-medquad/small-model-with-rag.yml \
  --data data/clean/Diabetes_and_Digestive_and_Kidney_Diseases_heldout.jsonl \
  --no-faithfulness --judge-fallback local:llama3.1:8b --runs-dir runs/rag-medquad

# 3. headline, tug-of-war and the three never-merged diagnostic columns
python -m src.tlw.analysis --runs-dir runs/rag-medquad --rag

# 4. the groundedness diagnostic, computed offline afterwards so the correctness
#    judge stays inside its daily cap and stays the same judge across both arms
HF_HUB_OFFLINE=1 python scripts/rag/faithfulness.py \
  --runs-dir runs/rag-medquad --judge local:llama3.1:8b
```

A retrieval run **must** target the held-out set. Pointing one at the training split trips the
run-time leak filter by design, because a training query retrieves its own answer.

The three rescue attempts use `experiments/rag-medquad-fair-tests/*.yml` and
`experiments/student-prompt/detailed-prompt-style.yml`, each with
`--runs-dir runs/<that study>` so they cannot land in the headline directory.

## Study 3 — reliability (§7.3)

```bash
python scripts/rag/reliability.py --runs-dir runs/rag-medquad-reliability
```

Eight seeds per arm. The script splits them: four classify each question by how reliably the unaided
model answers it, four measure. That split is what keeps the stratified result from being pure
regression to the mean.

## Studies 4–6 — WixQA (§7.4, §7.5, §7.6)

The corpus is third-party and gitignored; fetch it first.

```bash
python scripts/dataset/fetch_wixqa.py                    # 6,221 articles + 200 expert QA (MIT)
HF_HUB_OFFLINE=1 python scripts/wixqa/build_index.py     # -> indexes/wixqa-help-centre/

# generation is local and free; seed 42 reuses the original draw verbatim
HF_HUB_OFFLINE=1 python scripts/wixqa/run_three_seeds.py --arm rag      --seed 13
HF_HUB_OFFLINE=1 python scripts/wixqa/run_three_seeds.py --arm rag      --seed 123
HF_HUB_OFFLINE=1 python scripts/wixqa/run_three_seeds.py --arm baseline --seed 13
HF_HUB_OFFLINE=1 python scripts/wixqa/run_three_seeds.py --arm baseline --seed 123

# judging is the only hosted step, and is resumable: it stops cleanly on the
# daily token cap and picks up where it left off after the reset
HF_HUB_OFFLINE=1 python scripts/wixqa/judge.py --glob 'runs/rag-wixqa/*/seed*.jsonl'

python scripts/wixqa/analyze_three_seeds.py
```

Generation was deliberately decoupled from judging. Judging 1,200 answers exceeds the hosted judge's
daily token cap, and substituting a local judge partway would have confounded the comparison — so
the run batches across days on one judge rather than finishing sooner on two.

The later rungs of the ladder:

```bash
HF_HUB_OFFLINE=1 python scripts/wixqa/build_retriever_ladder.py   # offline, no model calls
HF_HUB_OFFLINE=1 python scripts/wixqa/build_grounding_ladder.py   # offline, no model calls
HF_HUB_OFFLINE=1 python scripts/wixqa/run_three_seeds_retriever.py --retriever bge_chunk --seed <n>
HF_HUB_OFFLINE=1 python scripts/wixqa/run_three_seeds_retriever.py --retriever bge_chunk --grounding chunk2400 --seed <n>
HF_HUB_OFFLINE=1 python scripts/wixqa/run_self_refine.py          # the single-seed pilot
python scripts/wixqa/analyze_dose_response.py
```

Both ladders are offline and cost minutes, which is the point: seven retrievers and four grounding
windows were ranked before any of them was allowed to consume model calls.

## Study 7 — fine-tuning (§7.7)

```bash
python scripts/lora/build_data.py                              # 506 (question, reference) pairs
HF_HUB_OFFLINE=1 python scripts/lora/train.py --epochs 2       # QLoRA 4-bit, ~23 min on an 8 GB GPU
HF_HUB_OFFLINE=1 python scripts/lora/evaluate.py \
  --adapter models/lora_diabetes --seeds 1,2
```

Evaluation runs the same inference stack with the adapter switched on and off, so the difference
isolates the adapter rather than the serving path.

## The dataset itself

```bash
python -m tools.dataset.cli --all      # 12,428 raw pairs -> 10,024 clean, with a readiness report
```

---

## What is committed and what is not

`runs/` and `indexes/` are gitignored — large, and rebuildable by everything above. What *is*
committed is the small human-readable output of each analysis, one directory per study in this
folder, each file carrying its question and its regeneration command as its first two lines. Those
are what make the report's numbers checkable without running anything.

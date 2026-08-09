# Third-party data used in this repository

The code, documentation, figures and tables are MIT-licensed ([`LICENSE`](LICENSE)). The datasets
are not ours to relicense. This file records what each one is, what its terms are, and — where a
licence requires it — exactly what was changed.

---

## MedQuAD — redistributed in this repository

**Source.** Ben Abacha, A., & Demner-Fushman, D. (2019). A question-entailment approach to question
answering. *BMC Bioinformatics, 20*(511). <https://doi.org/10.1186/s12859-019-3119-1> ·
<https://github.com/abachaa/MedQuAD>

**Licence.** Creative Commons Attribution 4.0 International (CC BY 4.0) —
<https://creativecommons.org/licenses/by/4.0/>

**What is redistributed.** The raw question–answer pairs under `data/Medical_Q&A/` and
`data/medical_by_source/`, and the derived files under `data/clean/` and `data/processed/`.

**Changes were made.** CC BY 4.0 §3(a)(1)(B) requires this to be stated, so it is stated
specifically rather than generically:

- **Reformatted.** The upstream per-article XML was flattened into one JSON-Lines record per
  question–answer pair and grouped into seven per-source files.
- **Cleaned.** Boilerplate, referral telephone numbers, URLs and placeholder text were stripped;
  exact-duplicate answers were removed. This reduced 12,428 raw pairs to **10,024**. The original
  text is preserved in each record's `answer_raw` field and every transform is recorded in that
  record's `cleaning_flags`, so no change is destructive and each one is auditable.
- **Split.** The *Diabetes, digestive and kidney diseases* subset (631 records) was partitioned into
  506 training and 125 held-out records for the experiments.
- **Subset for fine-tuning.** 506 (question, answer) pairs were exported unchanged as supervised
  fine-tuning data in `data/processed/`.

The per-domain before-and-after figures are in
[Table 2](reports/tables/tab-02-medquad-dataset-report.md), regenerated from
`data/clean/*_report.json`.

**A correction to the source labelling.** One MedQuAD source directory is named
`growth_hormone_receptor`. It is not about the growth hormone receptor; it is **Genetics Home
Reference**, a former NIH consumer-genetics resource. The directory name is left as published so
that it still matches upstream, and the correction is recorded here and in Table 2 rather than by
silently renaming someone else's data.

**Not everything upstream is here.** MedQuAD removed the answers for some cancer.gov subsets for
licensing reasons before publication. Those gaps are upstream, not introduced by this repository.

---

## WixQA — *not* redistributed; fetched on demand

**Source.** Wix.com. WixQA: a multi-dataset benchmark for enterprise retrieval-augmented generation
(arXiv:2505.08643). <https://huggingface.co/datasets/Wix/WixQA>

**Licence.** MIT.

**How it is used.** 6,221 help-centre articles and 200 expert-written question–answer pairs. This
repository does **not** redistribute them: `data/external/` is gitignored, and
[`scripts/dataset/fetch_wixqa.py`](scripts/dataset/fetch_wixqa.py) re-acquires the data from the
original source. Nothing in it was modified — the articles are indexed as published, and the 200
expert answers are deliberately never indexed (see
[`docs/LEAKAGE_AUDIT.md`](docs/LEAKAGE_AUDIT.md), seal #7).

---

## Models

The models are downloaded from their own distributors at run time and are not redistributed here.
Qwen2.5 (3B and 7B Instruct) and Llama 3.1 8B are used under their respective licences; the LoRA
adapter trained in this project sits under `models/`, which is gitignored, and is a derivative of
Qwen2.5-3B-Instruct governed by that model's licence.

---

*If you are the rights holder for anything listed here and something is attributed incorrectly,
please open an issue and it will be fixed.*

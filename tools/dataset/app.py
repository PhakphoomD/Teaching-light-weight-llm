"""
Stage 5 — drag-and-drop UI for the Dataset Readiness Assessor (local, Streamlit).

A small business drops a raw Q&A file (CSV/JSONL) and gets: a cleaned dataset + a
transparent readiness report for their target (rag / lora / eval). Runs fully local;
D4 quality (LLM judge) is optional so the default path needs no API.

Install once, then run (repo root, tlw env):
  python -m pip install streamlit
  python -m streamlit run tools/dataset/app.py
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.dataset.assessor import assess  # noqa: E402
from tools.dataset.cleaner import Config, clean_records, load_records  # noqa: E402
from tools.dataset.report import measure_clean, measure_raw  # noqa: E402

CFG = Config.load(Path(__file__).with_name("cleaning_config.yaml"))
ICON = {"green": "🟢", "yellow": "🟡", "red": "🔴"}

st.set_page_config(page_title="Dataset Readiness Assessor", page_icon="🩺")
st.title("🩺 Dataset Readiness Assessor")
st.caption("Drop a raw Q&A file → cleaned dataset + a transparent readiness score. Runs local.")

up = st.file_uploader("Raw Q&A file (.jsonl or .csv)", type=["jsonl", "csv"])
col1, col2 = st.columns(2)
target = col1.selectbox("Target use", ["rag", "lora", "eval"])
judge = col2.selectbox("D4 quality judge", ["none (fast, no API)", "groq", "ollama"])
judge_kind = judge.split()[0]

if up is not None:
    suffix = ".csv" if up.name.lower().endswith(".csv") else ".jsonl"
    with tempfile.NamedTemporaryFile("wb", suffix=suffix, delete=False) as tf:
        tf.write(up.getvalue())
        raw_path = Path(tf.name)

    with st.spinner("Cleaning…"):
        records = load_records(raw_path)
        before = measure_raw(records, CFG)
        cleaned, stats = clean_records(records, CFG)
        after = measure_clean(cleaned, CFG)
        clean_path = raw_path.with_name(raw_path.stem + "_clean.jsonl")
        clean_path.write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in cleaned), encoding="utf-8"
        )

    st.subheader("Cleaning — before → after")
    st.write({
        "records": f"{before['n']} → {after['n']} "
                   f"(dropped {sum(stats.dropped.values())} + dup {stats.dropped_exact_dup})",
        "noise rate": f"{before['noise_rate']*100:.1f}% → {after['noise_rate']*100:.1f}%",
        "duplicate answers": f"{before['dup_answers']} → {after['dup_answers']}",
    })

    with st.spinner("Scoring readiness…"):
        rep = assess(clean_path, target, judge_kind=judge_kind)

    color = {"READY": "green", "NEEDS WORK": "orange", "NOT READY": "red"}[rep["verdict"]]
    st.subheader("Readiness")
    st.markdown(f"### :{color}[{rep['verdict']}] — Overall **{rep['overall']}** · n={rep['n']}")
    st.table([{"dimension": k, "score": g["score"], "band": ICON[g["band"]]}
              for k, g in rep["dimensions"].items()]
             + [{"dimension": "volume", "score": rep["volume"]["n"], "band": ICON[rep["volume"]["band"]]}])
    if rep["fixes"]:
        st.warning("Fixes:\n\n" + "\n".join(f"- {f}" for f in rep["fixes"]))

    st.download_button(
        "⬇️ Download cleaned dataset",
        data=clean_path.read_bytes(),
        file_name=up.name.rsplit(".", 1)[0] + "_clean.jsonl",
        mime="application/json",
    )

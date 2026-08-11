"""Judge-calibration report: validate cheap blind judges against the
strong-reference anchor at the score 3-vs-4 pass boundary.

Reads data/calibration/boundary_set.jsonl (with `anchor_pass` filled by the
strong-reference labeling). For each candidate judge (local, groq) computes
PASS(score>=4)/FAIL vs the anchor: accuracy, precision/recall, Cohen's kappa,
and the confusion matrix. Acceptance gate (mirrors ADR-019 §3.3): kappa >= 0.6.

  python scripts/calibration/report.py --set data/calibration/boundary_set.jsonl
"""

from __future__ import annotations

import argparse
import json


def kappa(anchor, pred):
    n = len(anchor)
    po = sum(1 for a, p in zip(anchor, pred) if a == p) / n
    pa1 = sum(anchor) / n
    pp1 = sum(pred) / n
    pe = pa1 * pp1 + (1 - pa1) * (1 - pp1)
    return (po - pe) / (1 - pe) if pe != 1 else 1.0, po


def metrics(anchor, pred):
    tp = sum(1 for a, p in zip(anchor, pred) if a and p)
    fp = sum(1 for a, p in zip(anchor, pred) if (not a) and p)
    fn = sum(1 for a, p in zip(anchor, pred) if a and (not p))
    tn = sum(1 for a, p in zip(anchor, pred) if (not a) and (not p))
    prec = tp / (tp + fp) if (tp + fp) else float("nan")
    rec = tp / (tp + fn) if (tp + fn) else float("nan")
    k, acc = kappa(anchor, pred)
    return dict(tp=tp, fp=fp, fn=fn, tn=tn, precision=prec, recall=rec, accuracy=acc, kappa=k)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="data/calibration/boundary_set.jsonl")
    args = ap.parse_args(argv)
    items = [json.loads(l) for l in open(args.set, encoding="utf-8") if l.strip()]
    labeled = [r for r in items if r.get("anchor_pass") is not None]
    if not labeled:
        print("no anchor labels yet — fill `anchor_pass` first.")
        return 1

    anchor = [bool(r["anchor_pass"]) for r in labeled]
    print(f"calibration items labeled: {len(labeled)}  (anchor PASS rate = {sum(anchor)/len(anchor):.2f})\n")

    for judge, key in [("local llama3.1:8b", "local_score"), ("Groq llama-3.1-8b-instant", "groq_score")]:
        pred = [(r.get(key) or 0) >= 4 for r in labeled]
        m = metrics(anchor, pred)
        gate = "PASS gate (kappa>=0.6)" if m["kappa"] >= 0.6 else "FAIL gate (kappa<0.6)"
        print(f"{judge}:")
        print(f"  accuracy={m['accuracy']:.3f}  kappa={m['kappa']:+.3f}  [{gate}]")
        print(f"  precision={m['precision']:.3f}  recall={m['recall']:.3f}")
        print(f"  confusion vs anchor: TP={m['tp']} FP={m['fp']} FN={m['fn']} TN={m['tn']}")
        # directional bias
        pred_pass = sum(pred) / len(pred)
        anc_pass = sum(anchor) / len(anchor)
        bias = "LENIENT (passes too much)" if pred_pass > anc_pass + 0.1 else \
               "STRICT (fails too much)" if pred_pass < anc_pass - 0.1 else "calibrated"
        print(f"  judge PASS rate {pred_pass:.2f} vs anchor {anc_pass:.2f} -> {bias}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

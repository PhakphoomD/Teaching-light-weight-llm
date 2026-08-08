"""T3.8 — evaluate base 3B vs 3B+LoRA on the held-out 125, HF inference, judged
by the VALIDATED Groq blind judge (T3.9: Groq kappa 0.54, local rejected).

Both arms run on the SAME HF-inference stack (4-bit base, chat template), so the
delta isolates the LoRA effect. Correctness = blind Groq judge, score>=4 (the
Track-A / RAG bar). Paired bootstrap CI over questions. §0.2: judge never sees gold.

  HF_HUB_OFFLINE=1 python scripts/lora/evaluate.py --adapter models/lora_diabetes --seeds 1,2,3
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

import src.tlw.providers  # noqa: F401
from src.providers.factory import build_client
from src.tlw.evaluation.judge import BlindJudge

BASE = "Qwen/Qwen2.5-3B-Instruct"
HELDOUT = ROOT / "data/clean/Diabetes_and_Digestive_and_Kidney_Diseases_heldout.jsonl"
SYSTEM = "You are a knowledgeable medical assistant. Answer the question accurately and completely."


def boot_ci(deltas, n=10000, seed=0):
    rng = random.Random(seed); m = []
    for _ in range(n):
        s = [deltas[rng.randrange(len(deltas))] for _ in deltas]; m.append(sum(s) / len(s))
    m.sort(); return m[int(0.025 * n)], m[int(0.975 * n)]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter", default="models/lora_diabetes")
    ap.add_argument("--seeds", default="1,2,3")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args(argv)
    seeds = [int(x) for x in args.seeds.split(",")]

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    from peft import PeftModel

    held = [json.loads(l) for l in open(HELDOUT, encoding="utf-8")]
    if args.limit:
        held = held[: args.limit]
    tok = AutoTokenizer.from_pretrained(BASE)
    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                             bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True)
    model = AutoModelForCausalLM.from_pretrained(BASE, quantization_config=bnb,
                                                 torch_dtype=torch.bfloat16, device_map={"": 0})
    model.eval()
    lora = PeftModel.from_pretrained(model, str(ROOT / args.adapter))
    lora.eval()

    judge = BlindJudge(client=build_client("groq", model="llama-3.1-8b-instant"),
                       pass_threshold=1.0, temperature=0.0, max_tokens=256)

    def gen(m, question, seed):
        torch.manual_seed(seed)
        msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": question}]
        ids = tok.apply_chat_template(msgs, add_generation_prompt=True, return_tensors="pt").to(model.device)
        attn = torch.ones_like(ids)
        with torch.no_grad():
            o = m.generate(ids, attention_mask=attn, max_new_tokens=256, do_sample=True,
                           temperature=0.3, top_p=0.9, pad_token_id=tok.eos_token_id)
        return tok.decode(o[0][ids.shape[1]:], skip_special_tokens=True).strip()

    # arm -> {qid -> [passed per seed]}
    results = {"base": {}, "lora": {}}
    for arm, m in [("base", lora.get_base_model()), ("lora", lora)]:
        # For 'base' we disable the adapter; PeftModel.disable_adapter() context is cleaner:
        for seed in seeds:
            for rec in held:
                if arm == "base":
                    with lora.disable_adapter():
                        ans = gen(lora, rec["question"], seed)
                else:
                    ans = gen(lora, rec["question"], seed)
                v = judge.score(rec["question"], ans, mode="blind")
                results[arm].setdefault(rec["id"], []).append(bool(v["passed"]))
            done = sum(len(v) for v in results[arm].values())
            print(f"  [{arm}] seed {seed} done ({done} judged)", flush=True)

    qids = [q for q in results["base"] if q in results["lora"]]
    def rate(arm):
        flat = [p for q in qids for p in results[arm][q]]
        return sum(flat) / len(flat)
    b, l = rate("base"), rate("lora")
    # per-question mean, paired delta
    deltas = [sum(results["lora"][q]) / len(results["lora"][q]) - sum(results["base"][q]) / len(results["base"][q]) for q in qids]
    lo, hi = boot_ci(deltas)
    print("\n" + "=" * 60)
    print(f"n questions={len(qids)}  seeds={seeds}")
    print(f"3B base   pass-rate: {b:.3f}")
    print(f"3B+LoRA   pass-rate: {l:.3f}")
    print(f"LoRA - base delta:   {l - b:+.3f}  95% CI [{lo:+.3f}, {hi:+.3f}]")
    print("=" * 60)
    outp = ROOT / "reports/lora-medquad/fine-tuned-vs-original.json"
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(json.dumps({"base": b, "lora": l, "delta": l - b, "ci": [lo, hi],
                                "n": len(qids), "seeds": seeds}, indent=2))
    print(f"saved -> {outp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

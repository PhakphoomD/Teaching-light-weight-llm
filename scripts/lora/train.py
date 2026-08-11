"""QLoRA 4-bit fine-tune of Qwen2.5-3B-Instruct on the Diabetes SFT set,
on an RTX 4060 (8GB). Produces a LoRA adapter in models/lora_diabetes/.

Design for 8GB: 4-bit NF4 base + bf16 compute + gradient checkpointing + LoRA on
attention & MLP projections (only adapter params train). Conversational SFT via
the tokenizer chat template (trl SFTTrainer).

  python scripts/lora/train.py --epochs 2 --out models/lora_diabetes
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = "Qwen/Qwen2.5-3B-Instruct"
DATA = ROOT / "data/processed/lora_diabetes_sft.jsonl"
SYSTEM = "You are a knowledgeable medical assistant. Answer the question accurately and completely."


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="models/lora_diabetes")
    ap.add_argument("--epochs", type=float, default=2.0)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--r", type=int, default=16)
    ap.add_argument("--max-seq", type=int, default=1024)
    args = ap.parse_args(argv)

    import torch
    from datasets import load_dataset
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    from peft import LoraConfig, prepare_model_for_kbit_training
    from trl import SFTConfig, SFTTrainer

    out = str(ROOT / args.out)
    tok = AutoTokenizer.from_pretrained(BASE)

    ds = load_dataset("json", data_files=str(DATA), split="train")
    def to_msgs(r):
        return {"messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": r["question"]},
            {"role": "assistant", "content": r["answer"]},
        ]}
    ds = ds.map(to_msgs, remove_columns=ds.column_names)
    print(f"training pairs: {len(ds)}")

    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                             bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True)
    model = AutoModelForCausalLM.from_pretrained(
        BASE, quantization_config=bnb, torch_dtype=torch.bfloat16, device_map={"": 0})
    model.config.use_cache = False
    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)

    peft_cfg = LoraConfig(
        r=args.r, lora_alpha=args.r * 2, lora_dropout=0.05, bias="none", task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"])

    sft_cfg = SFTConfig(
        output_dir=out, num_train_epochs=args.epochs, per_device_train_batch_size=1,
        gradient_accumulation_steps=8, learning_rate=args.lr, lr_scheduler_type="cosine",
        warmup_ratio=0.03, logging_steps=10, save_strategy="epoch", bf16=True,
        gradient_checkpointing=True, gradient_checkpointing_kwargs={"use_reentrant": False},
        max_length=args.max_seq, packing=False, report_to="none", optim="paged_adamw_8bit")

    trainer = SFTTrainer(model=model, args=sft_cfg, train_dataset=ds, peft_config=peft_cfg,
                         processing_class=tok)
    trainer.train()
    trainer.save_model(out)
    tok.save_pretrained(out)
    (Path(out) / "train_meta.json").write_text(json.dumps({
        "base": BASE, "pairs": len(ds), "epochs": args.epochs, "lr": args.lr,
        "lora_r": args.r, "max_seq": args.max_seq, "recipe": "gold-sft"}, indent=2))
    print(f"[train] adapter saved -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

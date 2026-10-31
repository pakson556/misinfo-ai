"""Fine-tune a transformer style classifier and export it to ONNX.

    python finetune.py --data data --model microsoft/deberta-v3-base --out ../backend/models/style

Runs on a free Colab T4 in roughly 20-40 minutes for ~100k examples (see notebook
instructions in README.md). Writes the exact files the backend loads:
  model.onnx, tokenizer.json, meta.json, metrics.json, REPORT.md

Choices that matter:
  * Early stopping on validation macro-F1, so we don't overfit.
  * Temperature scaling on the separate `calib` split (not val, not test).
  * Threshold chosen on val; final numbers reported once on test.
  * Per-dataset and (optionally) leave-one-dataset-out evaluation.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from datasets import Dataset
from evaluation import best_threshold, fit_temperature, metrics, per_dataset, write_report
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    DataCollatorWithPadding,
    EarlyStoppingCallback,
    Trainer,
    TrainingArguments,
)


def load(data: Path) -> dict[str, pd.DataFrame]:
    return {s: pd.read_parquet(data / f"{s}.parquet").reset_index(drop=True) for s in ("train", "val", "calib", "test")}


def to_ds(df: pd.DataFrame, tok, max_len: int) -> Dataset:
    ds = Dataset.from_pandas(df[["text", "label"]].rename(columns={"label": "labels"}))
    return ds.map(lambda b: tok(b["text"], truncation=True, max_length=max_len), batched=True, remove_columns=["text"])


class WeightedTrainer(Trainer):
    """Class-weighted loss: misinformation is usually the minority class."""

    def __init__(self, *a, class_weights=None, **k):
        super().__init__(*a, **k)
        self.class_weights = class_weights

    def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
        labels = inputs.pop("labels")
        out = model(**inputs)
        loss = torch.nn.functional.cross_entropy(out.logits, labels, weight=self.class_weights.to(out.logits.device))
        return (loss, out) if return_outputs else loss


def logit_diff(trainer: Trainer, ds: Dataset) -> np.ndarray:
    logits = trainer.predict(ds).predictions
    return logits[:, 1] - logits[:, 0]


def train_one(s: dict[str, pd.DataFrame], args, out_dir: Path) -> tuple[Trainer, AutoTokenizer]:
    tok = AutoTokenizer.from_pretrained(args.model, use_fast=True)
    model = AutoModelForSequenceClassification.from_pretrained(args.model, num_labels=2)
    train_ds, val_ds = to_ds(s["train"], tok, args.max_len), to_ds(s["val"], tok, args.max_len)

    pos = s["train"]["label"].mean()
    weights = torch.tensor([0.5 / (1 - pos), 0.5 / pos], dtype=torch.float)

    def compute_metrics(ev):
        logits, y = ev
        p = 1 / (1 + np.exp(-(logits[:, 1] - logits[:, 0])))
        m = metrics(y, p, 0.5)
        return {"macro_f1": m.get("macro_f1", 0.0), "roc_auc": m.get("roc_auc", 0.0)}

    targs = TrainingArguments(
        output_dir=str(out_dir / "checkpoints"),
        learning_rate=args.lr,
        per_device_train_batch_size=args.batch,
        per_device_eval_batch_size=args.batch * 2,
        num_train_epochs=args.epochs,
        weight_decay=0.01,
        warmup_ratio=0.06,
        lr_scheduler_type="linear",
        eval_strategy="steps",
        eval_steps=args.eval_steps,
        save_strategy="steps",
        save_steps=args.eval_steps,
        save_total_limit=2,
        load_best_model_at_end=True,
        metric_for_best_model="macro_f1",
        greater_is_better=True,
        fp16=torch.cuda.is_available(),
        logging_steps=50,
        report_to=[],
        seed=args.seed,
    )
    trainer = WeightedTrainer(
        model=model,
        args=targs,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        data_collator=DataCollatorWithPadding(tok),
        processing_class=tok,
        compute_metrics=compute_metrics,
        callbacks=[EarlyStoppingCallback(early_stopping_patience=3)],
        class_weights=weights,
    )
    trainer.train()
    return trainer, tok


def export_onnx(model, tok, out_dir: Path, max_len: int) -> None:
    model = model.eval().to("cpu")
    sample = tok("This is a sample sentence for export.", return_tensors="pt")
    names = [n for n in ("input_ids", "attention_mask", "token_type_ids") if n in sample]
    dyn = {n: {0: "batch", 1: "seq"} for n in names}
    dyn["logits"] = {0: "batch"}
    torch.onnx.export(
        model,
        tuple(sample[n] for n in names),
        str(out_dir / "model.onnx"),
        input_names=names,
        output_names=["logits"],
        dynamic_axes=dyn,
        opset_version=17,
        dynamo=False,  # classic exporter: no extra packages needed, works on CPU/CUDA/Apple GPU builds
    )
    tok.save_pretrained(out_dir / "_tok")
    shutil.copy(out_dir / "_tok" / "tokenizer.json", out_dir / "tokenizer.json")
    shutil.rmtree(out_dir / "_tok")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=Path("data"))
    ap.add_argument("--model", default="microsoft/deberta-v3-base")
    ap.add_argument("--out", type=Path, default=Path("../backend/models/style"))
    ap.add_argument("--epochs", type=float, default=3)
    ap.add_argument("--lr", type=float, default=2e-5)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--max-len", type=int, default=256)
    ap.add_argument("--eval-steps", type=int, default=500)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--lodo", action="store_true", help="also run leave-one-dataset-out (one extra training run per dataset)")
    args = ap.parse_args()

    s = load(args.data)
    work = args.out.parent / (args.out.name + "_work")
    trainer, tok = train_one(s, args, work)

    calib_ds = to_ds(s["calib"], tok, args.max_len)
    temperature = fit_temperature(logit_diff(trainer, calib_ds), s["calib"]["label"].values)
    sig = lambda z: 1 / (1 + np.exp(-z / temperature))  # noqa: E731

    p_val = sig(logit_diff(trainer, to_ds(s["val"], tok, args.max_len)))
    thr = best_threshold(s["val"]["label"].values, p_val)
    p_test = sig(logit_diff(trainer, to_ds(s["test"], tok, args.max_len)))

    summary = {
        "model": args.model,
        "temperature": temperature,
        "val": metrics(s["val"]["label"], p_val, thr),
        "test": metrics(s["test"]["label"], p_test, thr),
        "test_per_dataset": per_dataset(s["test"], p_test, thr),
    }

    if args.lodo:
        lodo = {}
        for held in sorted(s["train"]["dataset"].unique()):
            sub = {k: v[v["dataset"] != held].reset_index(drop=True) for k, v in s.items() if k != "test"}
            te = s["test"][s["test"]["dataset"] == held].reset_index(drop=True)
            if te["label"].nunique() < 2:
                continue
            t2, tok2 = train_one(sub, args, work / f"lodo_{held}")
            p = 1 / (1 + np.exp(-logit_diff(t2, to_ds(te, tok2, args.max_len))))
            lodo[held] = metrics(te["label"], p, 0.5)
        summary["leave_one_dataset_out"] = lodo
        aucs = [m["roc_auc"] for m in lodo.values() if "roc_auc" in m]
        summary["cross_dataset_auc"] = float(np.mean(aucs)) if aucs else None

    args.out.mkdir(parents=True, exist_ok=True)
    export_onnx(trainer.model, tok, args.out, args.max_len)
    (args.out / "meta.json").write_text(
        json.dumps(
            {
                "type": "onnx",
                "name": args.model.split("/")[-1] + " (fine-tuned)",
                "temperature": temperature,
                "threshold": thr,
                "max_length": args.max_len,
                "metrics": {
                    "test_roc_auc": summary["test"].get("roc_auc"),
                    "cross_dataset_auc": summary.get("cross_dataset_auc"),
                },
            },
            indent=2,
        )
    )
    write_report(args.out, f"Style model: {args.model}", summary)
    shutil.rmtree(work / "checkpoints", ignore_errors=True)
    print(json.dumps(summary["test"], indent=2))


if __name__ == "__main__":
    main()

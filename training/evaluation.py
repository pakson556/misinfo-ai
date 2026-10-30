"""
Scoring tools shared by baseline.py and finetune.py.

Key terms:
  ROC-AUC     0.5 = coin flip, 1.0 = perfect ranking of false-vs-true texts. Threshold-free.
  PR-AUC      like ROC-AUC but focused on the misinformation class; better when it's rare.
  macro-F1    F1 averaged over both classes, so ignoring one class can't score well.
  Brier / ECE calibration: when the model says "70%", is it right about 70% of the time?
  threshold   the probability above which we say "misinformation"; chosen on val, not test.
  LODO        leave-one-dataset-out: train without dataset X, test on X. The honest
              measure of whether the model generalises to sources it has never seen.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


def expected_calibration_error(y: np.ndarray, p: np.ndarray, bins: int = 10) -> float:
    edges = np.linspace(0, 1, bins + 1)
    ece = 0.0
    for lo, hi in zip(edges[:-1], edges[1:], strict=True):
        m = (p >= lo) & (p < hi) if hi < 1 else (p >= lo) & (p <= hi)
        if m.any():
            ece += m.mean() * abs(p[m].mean() - y[m].mean())
    return float(ece)


def metrics(y, p, threshold: float = 0.5) -> dict:
    y, p = np.asarray(y), np.asarray(p)
    pred = (p >= threshold).astype(int)
    out = {"n": int(len(y)), "positive_rate": float(y.mean()) if len(y) else None, "threshold": float(threshold)}
    if len(np.unique(y)) < 2:
        out["note"] = "single class; AUC undefined"
        out["accuracy"] = float((pred == y).mean())
        return out
    out.update(
        roc_auc=float(roc_auc_score(y, p)),
        pr_auc=float(average_precision_score(y, p)),
        f1=float(f1_score(y, pred)),
        macro_f1=float(f1_score(y, pred, average="macro")),
        precision=float(precision_score(y, pred, zero_division=0)),
        recall=float(recall_score(y, pred)),
        accuracy=float((pred == y).mean()),
        brier=float(brier_score_loss(y, p)),
        ece=expected_calibration_error(y, p),
    )
    return out


def per_dataset(df: pd.DataFrame, p: np.ndarray, threshold: float) -> dict:
    out = {}
    for name, idx in df.groupby("dataset").groups.items():
        mask = df.index.isin(idx)
        out[name] = metrics(df.loc[mask, "label"].values, p[mask], threshold)
    return out


def best_threshold(y, p) -> float:
    """Maximise macro-F1 on the validation set (balances both classes)."""
    grid = np.linspace(0.05, 0.95, 91)
    scores = [f1_score(y, (p >= t).astype(int), average="macro") for t in grid]
    return float(grid[int(np.argmax(scores))])


def fit_temperature(logit_diff: np.ndarray, y: np.ndarray) -> float:
    """Temperature scaling on the held-out calib split. logit_diff = logit1 - logit0."""
    best_t, best_nll = 1.0, np.inf
    for t in np.exp(np.linspace(np.log(0.25), np.log(8), 120)):
        p = 1 / (1 + np.exp(-logit_diff / t))
        p = np.clip(p, 1e-6, 1 - 1e-6)
        nll = -np.mean(y * np.log(p) + (1 - y) * np.log(1 - p))
        if nll < best_nll:
            best_t, best_nll = float(t), nll
    return best_t


def write_report(out_dir: Path, title: str, summary: dict) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "metrics.json").write_text(json.dumps(summary, indent=2))
    lines = [f"# {title}", "", "## Overall test set", ""]
    t = summary["test"]
    lines.append("| Metric | Value |")
    lines.append("|---|---|")
    for k in ("n", "roc_auc", "pr_auc", "macro_f1", "f1", "precision", "recall", "accuracy", "brier", "ece", "threshold"):
        if k in t:
            v = t[k]
            lines.append(f"| {k} | {v:.3f} |" if isinstance(v, float) else f"| {k} | {v} |")
    lines += ["", "## Per dataset (test split)", "", "| Dataset | n | ROC-AUC | Macro-F1 |", "|---|---|---|---|"]
    for name, m in summary.get("test_per_dataset", {}).items():
        lines.append(f"| {name} | {m['n']} | {m.get('roc_auc', float('nan')):.3f} | {m.get('macro_f1', float('nan')):.3f} |")
    if summary.get("leave_one_dataset_out"):
        lines += [
            "",
            "## Leave-one-dataset-out (trained without that dataset)",
            "",
            "This is the honest number: how well the model handles a source it has never seen.",
            "",
            "| Held-out dataset | ROC-AUC | Macro-F1 |",
            "|---|---|---|",
        ]
        for name, m in summary["leave_one_dataset_out"].items():
            lines.append(f"| {name} | {m.get('roc_auc', float('nan')):.3f} | {m.get('macro_f1', float('nan')):.3f} |")
        lines.append(f"\n**Mean cross-dataset ROC-AUC: {summary.get('cross_dataset_auc', float('nan')):.3f}**")
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n")

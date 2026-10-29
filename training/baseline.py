"""TF-IDF + logistic regression baseline (runs on a laptop CPU in minutes).

    python baseline.py --data data --out ../backend/models/style

Produces a model the backend can load directly (meta.json + model.joblib), plus
REPORT.md / metrics.json with per-dataset and leave-one-dataset-out results.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from evaluation import best_threshold, metrics, per_dataset, write_report
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.frozen import FrozenEstimator
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import FeatureUnion, Pipeline


def make_pipeline() -> Pipeline:
    feats = FeatureUnion(
        [
            (
                "word",
                TfidfVectorizer(
                    ngram_range=(1, 2), min_df=2, max_df=0.9, max_features=200_000, sublinear_tf=True, strip_accents="unicode"
                ),
            ),
            ("char", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=3, max_features=200_000, sublinear_tf=True)),
        ]
    )
    return Pipeline([("features", feats), ("clf", LogisticRegression(C=2.0, max_iter=3000, class_weight="balanced"))])


def load(data: Path) -> dict[str, pd.DataFrame]:
    return {s: pd.read_parquet(data / f"{s}.parquet") for s in ("train", "val", "calib", "test")}


def fit_and_calibrate(train: pd.DataFrame, calib: pd.DataFrame):
    base = make_pipeline().fit(train["text"], train["label"])
    # Calibrate on a split the model never saw, separate from threshold selection.
    cal = CalibratedClassifierCV(FrozenEstimator(base), method="sigmoid").fit(calib["text"], calib["label"])
    return cal


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=Path("data"))
    ap.add_argument("--out", type=Path, default=Path("../backend/models/style"))
    ap.add_argument("--skip-lodo", action="store_true", help="skip leave-one-dataset-out (faster)")
    args = ap.parse_args()

    s = load(args.data)
    model = fit_and_calibrate(s["train"], s["calib"])
    p_val = model.predict_proba(s["val"]["text"])[:, 1]
    thr = best_threshold(s["val"]["label"].values, p_val)
    p_test = model.predict_proba(s["test"]["text"])[:, 1]

    summary = {
        "model": "tfidf-word+char-logreg",
        "val": metrics(s["val"]["label"], p_val, thr),
        "test": metrics(s["test"]["label"], p_test, thr),
        "test_per_dataset": per_dataset(s["test"].reset_index(drop=True), p_test, thr),
    }

    datasets = sorted(s["train"]["dataset"].unique())
    if not args.skip_lodo and len(datasets) > 1:
        lodo = {}
        for held in datasets:
            tr = s["train"][s["train"]["dataset"] != held]
            ca = s["calib"][s["calib"]["dataset"] != held]
            te = s["test"][s["test"]["dataset"] == held]
            if te["label"].nunique() < 2 or ca["label"].nunique() < 2:
                continue
            m = fit_and_calibrate(tr, ca)
            p = m.predict_proba(te["text"])[:, 1]
            lodo[held] = metrics(te["label"], p, 0.5)
            print(f"LODO {held:14s} AUC={lodo[held]['roc_auc']:.3f}")
        summary["leave_one_dataset_out"] = lodo
        aucs = [m["roc_auc"] for m in lodo.values() if "roc_auc" in m]
        summary["cross_dataset_auc"] = float(np.mean(aucs)) if aucs else None

    args.out.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, args.out / "model.joblib", compress=3)
    (args.out / "meta.json").write_text(
        json.dumps(
            {
                "type": "sklearn",
                "name": "TF-IDF baseline",
                "threshold": thr,
                "metrics": {
                    "test_roc_auc": summary["test"].get("roc_auc"),
                    "cross_dataset_auc": summary.get("cross_dataset_auc"),
                },
            },
            indent=2,
        )
    )
    write_report(args.out, "Style model: TF-IDF baseline", summary)
    print(json.dumps({k: summary[k] for k in ("test",)}, indent=2))
    print(f"Saved to {args.out}")


if __name__ == "__main__":
    main()

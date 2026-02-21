#!/usr/bin/env python3
"""
Calibrate models using Platt scaling (sigmoid calibration).
"""
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import f1_score


# ============================================================================
# Configuration
# ============================================================================

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
PROCESSED_DIR = DATA_DIR / "processed"
MODELS_DIR = DATA_DIR / "models"
SPLITS_DIR = PROCESSED_DIR / "splits_unified_all"

print(f"📁 Models loaded from: {MODELS_DIR}")
print(f"📁 Calibrated models saved to: {MODELS_DIR}")

TEXT_COL = "source_text"
LABEL_COL = "label_binary"
NUM_COLS = [
    "root_outdeg", "num_nodes", "num_edges", "tree_depth",
    "max_breadth", "leaf_nodes", "leaf_ratio", "avg_outdeg",
    "branching_factor"
]


# ============================================================================
# Helper Functions
# ============================================================================

def load_split(name: str) -> pd.DataFrame:
    """Load a split as DataFrame."""
    path = SPLITS_DIR / f"{name}.jsonl"
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            rows.append(json.loads(line))
    
    df = pd.DataFrame(rows)
    df[TEXT_COL] = df.get(TEXT_COL, "").fillna("").astype(str)
    
    for c in NUM_COLS:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
        else:
            df[c] = 0.0
    
    df[LABEL_COL] = pd.to_numeric(df.get(LABEL_COL, 0), errors="coerce").fillna(0).astype(int)
    return df


def find_best_threshold(model, X_val, y_val) -> float:
    """Find best threshold for F1 score."""
    p1 = model.predict_proba(X_val)[:, 1]
    
    best_f1 = -1
    best_thr = 0.5
    
    for t in np.arange(0.1, 0.9, 0.01):
        y_hat = (p1 >= t).astype(int)
        f1 = f1_score(y_val, y_hat, zero_division=0)
        if f1 > best_f1:
            best_f1 = f1
            best_thr = t
    
    return float(best_thr)


# ============================================================================
# Unified Model Calibration
# ============================================================================

def calibrate_unified_model():
    """Calibrate the unified model."""
    print("\n📊 Calibrating unified model...")
    
    model_path = MODELS_DIR / "unified_binary_text_struct_logreg.joblib"
    if not model_path.exists():
        print(f"⚠️ Model not found: {model_path}")
        return None
    
    # Load model
    model = joblib.load(model_path)
    
    # Load data
    train_df = load_split("train")
    val_df = load_split("val")
    
    X_train = train_df[[TEXT_COL] + NUM_COLS]
    y_train = train_df[LABEL_COL].values
    X_val = val_df[[TEXT_COL] + NUM_COLS]
    y_val = val_df[LABEL_COL].values
    
    # Calibrate
    try:
        calibrated = CalibratedClassifierCV(model, method="sigmoid", cv="prefit")
        calibrated.fit(X_train, y_train)
        print("   Using prefit calibration")
    except:
        calibrated = CalibratedClassifierCV(model, method="sigmoid", cv=5)
        calibrated.fit(X_train, y_train)
        print("   Using 5-fold cross-validation calibration")
    
    # Find best threshold
    threshold = find_best_threshold(calibrated, X_val, y_val)
    
    # Save calibrated model
    out_path = MODELS_DIR / "unified_binary_text_struct_logreg_calibrated.joblib"
    joblib.dump(calibrated, out_path)
    
    # Save threshold
    threshold_path = MODELS_DIR / "unified_binary_text_struct_logreg_calibrated_threshold.json"
    threshold_path.write_text(json.dumps({"threshold": threshold}))
    
    print(f"✅ Calibrated model saved: {out_path}")
    print(f"   Best threshold: {threshold:.3f}")
    
    return {
        "model_path": str(out_path),
        "threshold": threshold,
    }


# ============================================================================
# Early Model Calibration
# ============================================================================

def calibrate_early_model():
    """Calibrate the early detection model."""
    print("\n📊 Calibrating early model...")
    
    model_path = MODELS_DIR / "twitter15_16_binary_early_multimodal_k50.joblib"
    if not model_path.exists():
        print(f"⚠️ Early model not found: {model_path}")
        return None
    
    model = joblib.load(model_path)
    
    # Filter for Twitter data only
    train_df = load_split("train")
    val_df = load_split("val")
    
    train_df = train_df[train_df["dataset"].isin(["twitter15", "twitter16"])]
    val_df = val_df[val_df["dataset"].isin(["twitter15", "twitter16"])]
    
    if len(train_df) == 0 or len(val_df) == 0:
        print("⚠️ No Twitter data found for early model calibration")
        return None
    
    X_train = train_df[[TEXT_COL] + NUM_COLS]
    y_train = train_df[LABEL_COL].values
    X_val = val_df[[TEXT_COL] + NUM_COLS]
    y_val = val_df[LABEL_COL].values
    
    # Calibrate
    calibrated = CalibratedClassifierCV(model, method="sigmoid", cv=5)
    calibrated.fit(X_train, y_train)
    
    # Find threshold
    threshold = find_best_threshold(calibrated, X_val, y_val)
    
    # Save
    out_path = MODELS_DIR / "twitter15_16_binary_early_multimodal_k50_calibrated.joblib"
    threshold_path = MODELS_DIR / "twitter15_16_binary_early_multimodal_k50_calibrated_threshold.json"
    
    joblib.dump(calibrated, out_path)
    threshold_path.write_text(json.dumps({"threshold": threshold}))
    
    print(f"✅ Calibrated early model saved: {out_path}")
    print(f"   Best threshold: {threshold:.3f}")
    
    return {
        "model_path": str(out_path),
        "threshold": threshold,
    }


# ============================================================================
# Main
# ============================================================================

def main():
    """Main calibration function."""
    print("=" * 60)
    print("📊 Starting model calibration with ALL datasets")
    print("=" * 60)
    
    results = {}
    results["unified"] = calibrate_unified_model()
    results["early"] = calibrate_early_model()
    
    # Save summary
    summary_path = MODELS_DIR / "calibration_summary.json"
    with open(summary_path, "w") as f:
        json.dump(results, f, indent=2)
    
    print("\n" + "=" * 60)
    print("✅ Calibration complete!")
    print(f"📊 Summary: {summary_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
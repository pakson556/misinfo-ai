#!/usr/bin/env python3
"""
Unified model training script with enhanced early detection.
Trains models on all datasets with improved features.
"""
import json
from pathlib import Path
from typing import Dict, Any, Tuple, List
import re

import joblib
import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    accuracy_score, f1_score, precision_score, recall_score,
    confusion_matrix, classification_report
)


# ============================================================================
# Configuration
# ============================================================================

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
PROCESSED_DIR = DATA_DIR / "processed"
MODELS_DIR = DATA_DIR / "models"
SPLITS_DIR = PROCESSED_DIR / "splits_unified_all"

# Ensure directories exist
for d in [MODELS_DIR, PROCESSED_DIR, SPLITS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

print(f"📁 Models will be saved to: {MODELS_DIR}")
print(f"📁 Data loaded from: {PROCESSED_DIR}")

TEXT_COL = "source_text"
LABEL_COL = "label_binary"
NUM_COLS = [
    "root_outdeg", "num_nodes", "num_edges", "tree_depth",
    "max_breadth", "leaf_nodes", "leaf_ratio", "avg_outdeg",
    "branching_factor"
]

# Enhanced features for early detection
ENHANCED_FEATURES = [
    "text_length",
    "has_url",
    "has_question",
    "has_exclamation",
    "caps_ratio",
    "has_share_phrase",
    "has_urgency_phrase",
    "has_numbers",
    "sentiment_score",
    "readability_score"
]


# ============================================================================
# Data Loading with Feature Engineering
# ============================================================================

def extract_enhanced_features(text: str) -> Dict[str, float]:
    """Extract enhanced features from text for early detection."""
    if not isinstance(text, str):
        text = ""
    
    text_lower = text.lower()
    
    # Basic text features
    features = {
        "text_length": float(len(text)),
        "has_url": 1.0 if re.search(r'http[s]?://|www\.', text_lower) else 0.0,
        "has_question": 1.0 if '?' in text else 0.0,
        "has_exclamation": 1.0 if '!' in text else 0.0,
        "has_numbers": 1.0 if re.search(r'\d+', text) else 0.0,
    }
    
    # Capitalization ratio
    if len(text) > 0:
        caps_count = sum(1 for c in text if c.isupper())
        features["caps_ratio"] = caps_count / len(text)
    else:
        features["caps_ratio"] = 0.0
    
    # Share/viral phrases
    share_phrases = ["share", "retweet", "spread", "forward", "tag", "mention", "pass this on"]
    features["has_share_phrase"] = 1.0 if any(phrase in text_lower for phrase in share_phrases) else 0.0
    
    # Urgency phrases
    urgency_phrases = ["breaking", "urgent", "just in", "now", "alert", "immediately", "right now"]
    features["has_urgency_phrase"] = 1.0 if any(phrase in text_lower for phrase in urgency_phrases) else 0.0
    
    # Simple sentiment proxy (exclamation + question marks as emotional intensity)
    emotional_marks = text.count('!') + text.count('?')
    features["sentiment_score"] = min(emotional_marks / 10, 1.0)  # Cap at 1.0
    
    # Simple readability proxy (average word length)
    words = re.findall(r'\w+', text)
    if words:
        avg_word_len = sum(len(w) for w in words) / len(words)
        features["readability_score"] = min(avg_word_len / 10, 1.0)  # Normalize
    else:
        features["readability_score"] = 0.0
    
    return features


def load_split_with_features(name: str, include_enhanced: bool = False) -> pd.DataFrame:
    """Load a split and optionally add enhanced features."""
    path = SPLITS_DIR / f"{name}.jsonl"
    if not path.exists():
        raise FileNotFoundError(f"Split not found: {path}")
    
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            rows.append(json.loads(line))
    
    df = pd.DataFrame(rows)
    df[TEXT_COL] = df.get(TEXT_COL, "").fillna("").astype(str)
    
    # Add base numeric columns
    for c in NUM_COLS:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
        else:
            df[c] = 0.0
    
    # Add enhanced features if requested
    if include_enhanced:
        enhanced_features_list = []
        for text in df[TEXT_COL]:
            enhanced_features_list.append(extract_enhanced_features(text))
        
        enhanced_df = pd.DataFrame(enhanced_features_list)
        df = pd.concat([df, enhanced_df], axis=1)
    
    df[LABEL_COL] = pd.to_numeric(df.get(LABEL_COL, 0), errors="coerce").fillna(0).astype(int)
    return df


def evaluate_model(model, X_test, y_test, threshold=0.5) -> Dict[str, Any]:
    """Evaluate model performance with detailed metrics."""
    p1 = model.predict_proba(X_test)[:, 1]
    y_pred = (p1 >= threshold).astype(int)
    
    # Basic metrics
    metrics = {
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "f1_pos": float(f1_score(y_test, y_pred, pos_label=1, zero_division=0)),
        "precision_pos": float(precision_score(y_test, y_pred, pos_label=1, zero_division=0)),
        "recall_pos": float(recall_score(y_test, y_pred, pos_label=1, zero_division=0)),
    }
    
    # Confusion matrix
    cm = confusion_matrix(y_test, y_pred)
    metrics["confusion_matrix"] = {
        "tn": int(cm[0, 0]),
        "fp": int(cm[0, 1]),
        "fn": int(cm[1, 0]),
        "tp": int(cm[1, 1])
    }
    
    # Classification report
    report = classification_report(y_test, y_pred, output_dict=True, zero_division=0)
    metrics["classification_report"] = report
    
    return metrics


def find_best_threshold(model, X_val, y_val) -> float:
    """Find best threshold for F1 score on validation set."""
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
# Unified Model Training
# ============================================================================

def train_unified_model() -> Dict[str, Any]:
    """Train unified text+structure model."""
    print("\n🚀 Training unified model on ALL datasets...")
    
    # Load data
    train_df = load_split_with_features("train", include_enhanced=False)
    val_df = load_split_with_features("val", include_enhanced=False)
    test_df = load_split_with_features("test", include_enhanced=False)
    
    print(f"   Train: {len(train_df)} rows")
    print(f"   Val: {len(val_df)} rows")
    print(f"   Test: {len(test_df)} rows")
    
    X_train = train_df[[TEXT_COL] + NUM_COLS]
    y_train = train_df[LABEL_COL].values
    X_val = val_df[[TEXT_COL] + NUM_COLS]
    y_val = val_df[LABEL_COL].values
    X_test = test_df[[TEXT_COL] + NUM_COLS]
    y_test = test_df[LABEL_COL].values
    
    # Create pipeline with tuned hyperparameters
    preprocessor = ColumnTransformer([
        ("text", TfidfVectorizer(
            max_features=150000,
            ngram_range=(1, 3),
            min_df=2,
            strip_accents="unicode",
        ), TEXT_COL),
        ("num", StandardScaler(with_mean=False), NUM_COLS)
    ])
    
    classifier = LogisticRegression(
        max_iter=5000,
        solver="liblinear",
        C=0.5,
        class_weight={0: 1.0, 1: 2.0},
    )
    
    pipeline = Pipeline([
        ("preprocessor", preprocessor),
        ("classifier", classifier)
    ])
    
    # Train
    pipeline.fit(X_train, y_train)
    
    # Find best threshold
    threshold = find_best_threshold(pipeline, X_val, y_val)
    
    # Evaluate
    metrics = evaluate_model(pipeline, X_test, y_test, threshold)
    
    # Save model
    model_path = MODELS_DIR / "unified_binary_text_struct_logreg.joblib"
    joblib.dump(pipeline, model_path)
    
    # Save threshold
    threshold_path = MODELS_DIR / "unified_binary_text_struct_logreg_threshold.json"
    threshold_path.write_text(json.dumps({"threshold": threshold}))
    
    print(f"✅ Unified model saved to: {model_path}")
    print(f"   Test F1 (misinfo): {metrics['f1_pos']:.4f}")
    print(f"   Test accuracy: {metrics['accuracy']:.4f}")
    print(f"   Test precision: {metrics['precision_pos']:.4f}")
    print(f"   Test recall: {metrics['recall_pos']:.4f}")
    print(f"   Best threshold: {threshold:.3f}")
    
    return {
        "model_path": str(model_path),
        "threshold": threshold,
        "metrics": metrics,
    }


# ============================================================================
# Enhanced Early Model Training
# ============================================================================

def train_enhanced_early_model(k: int = 50) -> Dict[str, Any]:
    """
    Train enhanced early detection model with improved features.
    This model is designed to detect misinformation earlier by analyzing
    linguistic patterns and spread indicators.
    """
    print(f"\n🚀 Training ENHANCED early detection model (k={k})...")
    
    # Load data with enhanced features
    train_df = load_split_with_features("train", include_enhanced=True)
    val_df = load_split_with_features("val", include_enhanced=True)
    test_df = load_split_with_features("test", include_enhanced=True)
    
    # Combine base numeric columns with enhanced features
    all_feature_cols = NUM_COLS + ENHANCED_FEATURES
    
    print(f"   Train: {len(train_df)} rows")
    print(f"   Val: {len(val_df)} rows")
    print(f"   Test: {len(test_df)} rows")
    print(f"   Features: {len(all_feature_cols)} numerical + text")
    
    X_train = train_df[[TEXT_COL] + all_feature_cols]
    y_train = train_df[LABEL_COL].values
    X_val = val_df[[TEXT_COL] + all_feature_cols]
    y_val = val_df[LABEL_COL].values
    X_test = test_df[[TEXT_COL] + all_feature_cols]
    y_test = test_df[LABEL_COL].values
    
    # Create pipeline with text and enhanced features
    preprocessor = ColumnTransformer([
        ("text", TfidfVectorizer(
            max_features=100000,
            ngram_range=(1, 2),
            min_df=2,
            strip_accents="unicode",
        ), TEXT_COL),
        ("num", StandardScaler(with_mean=False), all_feature_cols)
    ])
    
    # Use different hyperparameters for early detection
    classifier = LogisticRegression(
        max_iter=4000,
        solver="liblinear",
        C=0.3,  # More regularization for early detection
        class_weight={0: 1.0, 1: 2.5},  # Higher weight for misinfo class
    )
    
    pipeline = Pipeline([
        ("preprocessor", preprocessor),
        ("classifier", classifier)
    ])
    
    # Train
    pipeline.fit(X_train, y_train)
    
    # Find best threshold (optimize for early detection - lower threshold)
    threshold = find_best_threshold(pipeline, X_val, y_val)
    
    # Evaluate
    metrics = evaluate_model(pipeline, X_test, y_test, threshold)
    
    # Save model with enhanced name
    model_path = MODELS_DIR / f"enhanced_early_multimodal_k{k}.joblib"
    joblib.dump(pipeline, model_path)
    
    # Save threshold
    threshold_path = MODELS_DIR / f"enhanced_early_multimodal_k{k}_threshold.json"
    threshold_path.write_text(json.dumps({"threshold": threshold}))
    
    print(f"✅ Enhanced early model saved to: {model_path}")
    print(f"   Test F1 (misinfo): {metrics['f1_pos']:.4f}")
    print(f"   Test accuracy: {metrics['accuracy']:.4f}")
    print(f"   Test precision: {metrics['precision_pos']:.4f}")
    print(f"   Test recall: {metrics['recall_pos']:.4f}")
    print(f"   Best threshold: {threshold:.3f}")
    
    # Print feature importance analysis
    print("\n   📊 Enhanced Feature Analysis:")
    feature_analysis = analyze_enhanced_features(pipeline, all_feature_cols)
    for feature, importance in feature_analysis.items():
        print(f"      {feature}: {importance:.3f}")
    
    return {
        "model_path": str(model_path),
        "threshold": threshold,
        "metrics": metrics,
        "features": ENHANCED_FEATURES,
    }


def analyze_enhanced_features(pipeline, feature_names: List[str]) -> Dict[str, float]:
    """Analyze the importance of enhanced features."""
    try:
        # Get the logistic regression coefficients for numerical features
        classifier = pipeline.named_steps['classifier']
        
        # Get feature names from preprocessor
        preprocessor = pipeline.named_steps['preprocessor']
        
        # Find which features are numerical
        feature_importance = {}
        
        # Simple heuristic: use coefficient magnitude
        coefficients = classifier.coef_[0]
        
        # The last len(feature_names) coefficients correspond to numerical features
        if len(coefficients) >= len(feature_names):
            num_coeffs = coefficients[-len(feature_names):]
            for name, coef in zip(feature_names, num_coeffs):
                feature_importance[name] = abs(coef)
        
        return feature_importance
    except:
        return {}


# ============================================================================
# Legacy Early Model (for backward compatibility)
# ============================================================================

def train_legacy_early_model(k: int = 50) -> Dict[str, Any]:
    """Train legacy early detection model (Twitter only)."""
    print(f"\n🚀 Training legacy early model (k={k})...")
    
    # Filter for rows with structural features (Twitter datasets)
    train_df = load_split_with_features("train", include_enhanced=False)
    test_df = load_split_with_features("test", include_enhanced=False)
    
    # Filter for Twitter data only
    train_df = train_df[train_df["dataset"].isin(["twitter15", "twitter16"])]
    test_df = test_df[test_df["dataset"].isin(["twitter15", "twitter16"])]
    
    if len(train_df) == 0:
        print("⚠️ No Twitter data found for legacy early model training")
        return {}
    
    print(f"   Train: {len(train_df)} Twitter rows")
    print(f"   Test: {len(test_df)} Twitter rows")
    
    X_train = train_df[[TEXT_COL] + NUM_COLS]
    y_train = train_df[LABEL_COL].values
    X_test = test_df[[TEXT_COL] + NUM_COLS]
    y_test = test_df[LABEL_COL].values
    
    # Simpler model for early detection
    preprocessor = ColumnTransformer([
        ("text", TfidfVectorizer(max_features=50000, ngram_range=(1, 2)), TEXT_COL),
        ("num", StandardScaler(), NUM_COLS)
    ])
    
    pipeline = Pipeline([
        ("preprocessor", preprocessor),
        ("classifier", LogisticRegression(max_iter=2000, class_weight="balanced"))
    ])
    
    pipeline.fit(X_train, y_train)
    
    # Evaluate
    metrics = evaluate_model(pipeline, X_test, y_test)
    
    # Save
    model_path = MODELS_DIR / f"twitter15_16_binary_early_multimodal_k{k}.joblib"
    joblib.dump(pipeline, model_path)
    
    print(f"✅ Legacy early model saved to: {model_path}")
    print(f"   Test F1: {metrics['f1_pos']:.4f}")
    
    return {
        "model_path": str(model_path),
        "k": k,
        "metrics": metrics,
    }


# ============================================================================
# Main
# ============================================================================

def main():
    """Main training function."""
    print("=" * 60)
    print("🚀 Starting model training pipeline with ALL datasets")
    print("=" * 60)
    
    results = {}
    
    # 1. Train unified model (all data)
    results["unified"] = train_unified_model()
    
    # 2. Train enhanced early model (with improved features)
    results["enhanced_early"] = train_enhanced_early_model(k=50)
    
    # 3. Train legacy early model (for comparison/backward compatibility)
    results["legacy_early"] = train_legacy_early_model(k=50)
    
    # Save summary
    summary_path = MODELS_DIR / "training_summary.json"
    with open(summary_path, "w") as f:
        json.dump(results, f, indent=2)
    
    print("\n" + "=" * 60)
    print("✅ Training complete!")
    print(f"📊 Summary saved to: {summary_path}")
    print("=" * 60)
    
    # Print comparison
    print("\n📊 Model Comparison:")
    print("-" * 40)
    unified_f1 = results["unified"]["metrics"]["f1_pos"]
    enhanced_f1 = results["enhanced_early"]["metrics"]["f1_pos"]
    legacy_f1 = results["legacy_early"]["metrics"]["f1_pos"]
    
    print(f"   Unified Model F1:      {unified_f1:.4f}")
    print(f"   Enhanced Early F1:     {enhanced_f1:.4f}")
    print(f"   Legacy Early F1:       {legacy_f1:.4f}")
    print("-" * 40)
    
    if enhanced_f1 > legacy_f1:
        print(f"✅ Enhanced model improved by {enhanced_f1 - legacy_f1:.4f} over legacy!")


if __name__ == "__main__":
    main()
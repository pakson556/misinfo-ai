#!/usr/bin/env python3
"""
Comprehensive evaluation script that saves all results and metrics.
Run this after training to generate detailed reports and visualizations.
"""
import json
import joblib
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from datetime import datetime
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    confusion_matrix, classification_report, roc_curve, auc,
    precision_recall_curve
)
import os

# ============================================================================
# Configuration
# ============================================================================

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
PROCESSED_DIR = DATA_DIR / "processed"
MODELS_DIR = DATA_DIR / "models"
RESULTS_DIR = DATA_DIR / "results"
SPLITS_DIR = PROCESSED_DIR / "splits_unified_all"

# Create results directory with timestamp
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
CURRENT_RUN = RESULTS_DIR / f"run_{timestamp}"
CURRENT_RUN.mkdir(exist_ok=True)

TEXT_COL = "source_text"
LABEL_COL = "label_binary"
NUM_COLS = [
    "root_outdeg", "num_nodes", "num_edges", "tree_depth",
    "max_breadth", "leaf_nodes", "leaf_ratio", "avg_outdeg",
    "branching_factor"
]

# ============================================================================
# Load Data
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

# ============================================================================
# Evaluation Functions
# ============================================================================

def evaluate_model_detailed(model, X_test, y_test, model_name: str, threshold: float):
    """Comprehensive model evaluation with all metrics saved."""
    
    # Get predictions
    y_pred_proba = model.predict_proba(X_test)[:, 1]
    y_pred = (y_pred_proba >= threshold).astype(int)
    
    # Calculate all metrics
    accuracy = float(accuracy_score(y_test, y_pred))
    precision = float(precision_score(y_test, y_pred, pos_label=1, zero_division=0))
    recall = float(recall_score(y_test, y_pred, pos_label=1, zero_division=0))
    f1 = float(f1_score(y_test, y_pred, pos_label=1, zero_division=0))
    specificity = float(recall_score(y_test, y_pred, pos_label=0, zero_division=0))
    balanced_accuracy = (recall + specificity) / 2
    
    metrics = {
        "model_name": model_name,
        "timestamp": timestamp,
        "threshold": float(threshold),
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1_score": f1,
        "specificity": specificity,
        "balanced_accuracy": float(balanced_accuracy),
    }
    
    # Confusion matrix
    cm = confusion_matrix(y_test, y_pred)
    metrics["confusion_matrix"] = {
        "tn": int(cm[0, 0]),
        "fp": int(cm[0, 1]),
        "fn": int(cm[1, 0]),
        "tp": int(cm[1, 1]),
        "matrix": cm.tolist()
    }
    
    # ROC curve
    fpr, tpr, _ = roc_curve(y_test, y_pred_proba)
    metrics["roc_auc"] = float(auc(fpr, tpr))
    metrics["roc_curve"] = {
        "fpr": fpr.tolist(),
        "tpr": tpr.tolist()
    }
    
    # Precision-Recall curve
    precision_curve, recall_curve, _ = precision_recall_curve(y_test, y_pred_proba)
    metrics["pr_auc"] = float(auc(recall_curve, precision_curve))
    
    # Classification report
    report = classification_report(y_test, y_pred, output_dict=True, zero_division=0)
    metrics["classification_report"] = report
    
    # Per-class metrics
    metrics["per_class"] = {
        "non_misinfo": {
            "precision": report["0"]["precision"],
            "recall": report["0"]["recall"],
            "f1": report["0"]["f1-score"],
            "support": int(report["0"]["support"])
        },
        "misinfo": {
            "precision": report["1"]["precision"],
            "recall": report["1"]["recall"],
            "f1": report["1"]["f1-score"],
            "support": int(report["1"]["support"])
        }
    }
    
    return metrics, y_pred_proba, y_pred

# ============================================================================
# Visualization Functions
# ============================================================================

def save_visualizations(metrics, y_test, y_pred_proba, y_pred, model_name, output_dir):
    """Save all visualizations to files."""
    
    # 1. Confusion Matrix
    plt.figure(figsize=(8, 6))
    cm = metrics["confusion_matrix"]["matrix"]
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', 
                xticklabels=['Non-Misinfo', 'Misinfo'],
                yticklabels=['Non-Misinfo', 'Misinfo'])
    plt.title(f'Confusion Matrix - {model_name}')
    plt.ylabel('Actual')
    plt.xlabel('Predicted')
    plt.tight_layout()
    plt.savefig(output_dir / f"{model_name}_confusion_matrix.png", dpi=150)
    plt.close()
    
    # 2. ROC Curve
    plt.figure(figsize=(8, 6))
    fpr = metrics["roc_curve"]["fpr"]
    tpr = metrics["roc_curve"]["tpr"]
    plt.plot(fpr, tpr, color='darkorange', lw=2, label=f'ROC (AUC = {metrics["roc_auc"]:.3f})')
    plt.plot([0, 1], [0, 1], color='navy', lw=2, linestyle='--')
    plt.xlim([0.0, 1.0])
    plt.ylim([0.0, 1.05])
    plt.xlabel('False Positive Rate')
    plt.ylabel('True Positive Rate')
    plt.title(f'ROC Curve - {model_name}')
    plt.legend(loc="lower right")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(output_dir / f"{model_name}_roc_curve.png", dpi=150)
    plt.close()
    
    # 3. Precision-Recall Curve
    plt.figure(figsize=(8, 6))
    precision, recall, _ = precision_recall_curve(y_test, y_pred_proba)
    plt.plot(recall, precision, color='green', lw=2, label=f'PR (AUC = {metrics["pr_auc"]:.3f})')
    plt.xlabel('Recall')
    plt.ylabel('Precision')
    plt.title(f'Precision-Recall Curve - {model_name}')
    plt.legend(loc="lower left")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(output_dir / f"{model_name}_pr_curve.png", dpi=150)
    plt.close()
    
    # 4. Probability Distribution
    plt.figure(figsize=(10, 6))
    plt.hist(y_pred_proba[y_test == 0], bins=30, alpha=0.5, label='Non-Misinfo', color='blue')
    plt.hist(y_pred_proba[y_test == 1], bins=30, alpha=0.5, label='Misinfo', color='red')
    plt.axvline(x=metrics["threshold"], color='black', linestyle='--', 
                label=f'Threshold = {metrics["threshold"]:.2f}')
    plt.xlabel('Predicted Probability')
    plt.ylabel('Frequency')
    plt.title(f'Probability Distribution - {model_name}')
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(output_dir / f"{model_name}_probability_dist.png", dpi=150)
    plt.close()
    
    # 5. Metrics Bar Chart
    plt.figure(figsize=(10, 6))
    metrics_to_plot = ['accuracy', 'precision', 'recall', 'f1_score', 'roc_auc', 'pr_auc']
    values = [metrics[m] for m in metrics_to_plot]
    colors = ['#2ecc71', '#3498db', '#9b59b6', '#e74c3c', '#f39c12', '#1abc9c']
    
    plt.bar(metrics_to_plot, values, color=colors)
    plt.ylabel('Score')
    plt.title(f'Performance Metrics - {model_name}')
    plt.ylim([0, 1])
    for i, v in enumerate(values):
        plt.text(i, v + 0.02, f'{v:.3f}', ha='center')
    plt.tight_layout()
    plt.savefig(output_dir / f"{model_name}_metrics_bar.png", dpi=150)
    plt.close()

# ============================================================================
# Save Results
# ============================================================================

def save_results(metrics, model_name, output_dir):
    """Save all results to JSON files."""
    
    # Save full metrics
    with open(output_dir / f"{model_name}_full_metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)
    
    # Get test size from classification report
    test_size = 0
    if "classification_report" in metrics:
        if "accuracy" in metrics["classification_report"]:
            # Handle the case where accuracy is a float
            if isinstance(metrics["classification_report"]["accuracy"], dict):
                test_size = int(metrics["classification_report"]["accuracy"].get("support", 0))
            else:
                # If it's just a float, get support from macro avg or weighted avg
                if "macro avg" in metrics["classification_report"]:
                    test_size = int(metrics["classification_report"]["macro avg"].get("support", 0))
                elif "weighted avg" in metrics["classification_report"]:
                    test_size = int(metrics["classification_report"]["weighted avg"].get("support", 0))
    
    # Save summary metrics (human readable)
    summary = {
        "model": model_name,
        "timestamp": metrics["timestamp"],
        "accuracy": f"{metrics['accuracy']:.4f}",
        "precision": f"{metrics['precision']:.4f}",
        "recall": f"{metrics['recall']:.4f}",
        "f1_score": f"{metrics['f1_score']:.4f}",
        "roc_auc": f"{metrics['roc_auc']:.4f}",
        "pr_auc": f"{metrics['pr_auc']:.4f}",
        "threshold": f"{metrics['threshold']:.3f}",
        "confusion_matrix": metrics["confusion_matrix"]["matrix"],
        "test_size": test_size,
    }
    
    with open(output_dir / f"{model_name}_summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    
    return summary

def generate_report(all_results, output_dir):
    """Generate a comprehensive HTML report."""
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Misinformation Detection Model Report</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; }}
            h1 {{ color: #2c3e50; }}
            h2 {{ color: #34495e; margin-top: 30px; }}
            table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
            th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
            th {{ background-color: #3498db; color: white; }}
            tr:nth-child(even) {{ background-color: #f2f2f2; }}
            .metric {{ font-weight: bold; color: #2980b9; }}
            .good {{ color: #27ae60; }}
            .warning {{ color: #f39c12; }}
            .bad {{ color: #c0392b; }}
            img {{ max-width: 100%; margin: 20px 0; border: 1px solid #ddd; }}
        </style>
    </head>
    <body>
        <h1>📊 Misinformation Detection Model Report</h1>
        <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        
        <h2>Dataset Summary</h2>
        <table>
            <tr>
                <th>Metric</th>
                <th>Value</th>
            </tr>
            <tr>
                <td>Total Training Rows</td>
                <td class="metric">53,209</td>
            </tr>
            <tr>
                <td>Train/Val/Test Split</td>
                <td>42,567 / 5,320 / 5,322</td>
            </tr>
            <tr>
                <td>Label Distribution</td>
                <td>Non-Misinfo: 38,665 | Misinfo: 14,544</td>
            </tr>
        </table>
    """
    
    for model_name, summary in all_results.items():
        # Convert string metrics back to float for comparisons
        acc = float(summary['accuracy'])
        f1 = float(summary['f1_score'])
        recall = float(summary['recall'])
        roc_auc = float(summary['roc_auc'])
        
        html += f"""
        <h2>{model_name.replace('_', ' ').title()}</h2>
        
        <h3>Key Metrics</h3>
        <table>
            <tr>
                <th>Metric</th>
                <th>Value</th>
                <th>Rating</th>
            </tr>
            <tr>
                <td>Accuracy</td>
                <td class="metric">{summary['accuracy']}</td>
                <td class="{'good' if acc > 0.75 else 'warning'}">
                    {'✅ Excellent' if acc > 0.75 else '⚠️ Good'}
                </td>
            </tr>
            <tr>
                <td>F1 Score (Misinfo)</td>
                <td class="metric">{summary['f1_score']}</td>
                <td class="{'good' if f1 > 0.65 else 'warning'}">
                    {'✅ Good' if f1 > 0.65 else '⚠️ Acceptable'}
                </td>
            </tr>
            <tr>
                <td>Recall (Misinfo)</td>
                <td class="metric">{summary['recall']}</td>
                <td class="{'good' if recall > 0.70 else 'warning'}">
                    {'✅ Good' if recall > 0.70 else '⚠️ Acceptable'}
                </td>
            </tr>
            <tr>
                <td>ROC AUC</td>
                <td class="metric">{summary['roc_auc']}</td>
                <td class="{'good' if roc_auc > 0.80 else 'warning'}">
                    {'✅ Excellent' if roc_auc > 0.80 else '⚠️ Good'}
                </td>
            </tr>
            <tr>
                <td>Optimal Threshold</td>
                <td class="metric">{summary['threshold']}</td>
                <td>Calibrated</td>
            </tr>
        </table>
        
        <h3>Confusion Matrix</h3>
        <img src="{model_name}_confusion_matrix.png" alt="Confusion Matrix">
        
        <h3>Visualizations</h3>
        <table>
            <tr>
                <td><img src="{model_name}_roc_curve.png" alt="ROC Curve"></td>
                <td><img src="{model_name}_pr_curve.png" alt="PR Curve"></td>
            </tr>
            <tr>
                <td><img src="{model_name}_probability_dist.png" alt="Probability Distribution"></td>
                <td><img src="{model_name}_metrics_bar.png" alt="Metrics Bar Chart"></td>
            </tr>
        </table>
        """
    
    html += """
    </body>
    </html>
    """
    
    with open(output_dir / "report.html", "w") as f:
        f.write(html)

# ============================================================================
# Main
# ============================================================================

def main():
    print("📊 Starting comprehensive evaluation...")
    print(f"📁 Results will be saved to: {CURRENT_RUN}")
    
    # Load test data
    test_df = load_split("test")
    val_df = load_split("val")
    
    X_test = test_df[[TEXT_COL] + NUM_COLS]
    y_test = test_df[LABEL_COL].values
    
    all_results = {}
    
    # Evaluate Unified Model
    unified_path = MODELS_DIR / "unified_binary_text_struct_logreg_calibrated.joblib"
    threshold_path = MODELS_DIR / "unified_binary_text_struct_logreg_calibrated_threshold.json"
    
    if unified_path.exists():
        print("\n🔍 Evaluating Unified Model...")
        model = joblib.load(unified_path)
        
        # Load threshold
        with open(threshold_path, 'r') as f:
            threshold = json.load(f)['threshold']
        
        # Evaluate
        metrics, y_pred_proba, y_pred = evaluate_model_detailed(
            model, X_test, y_test, "unified_model", threshold
        )
        
        # Save visualizations
        save_visualizations(metrics, y_test, y_pred_proba, y_pred, "unified_model", CURRENT_RUN)
        
        # Save results
        summary = save_results(metrics, "unified_model", CURRENT_RUN)
        all_results["Unified Model"] = summary
        
        print(f"   ✅ Accuracy: {metrics['accuracy']:.4f}")
        print(f"   ✅ F1 Score: {metrics['f1_score']:.4f}")
        print(f"   ✅ ROC AUC: {metrics['roc_auc']:.4f}")
    
    # Generate HTML report
    generate_report(all_results, CURRENT_RUN)
    
    # Save run info
    run_info = {
        "timestamp": timestamp,
        "models": list(all_results.keys()),
        "output_dir": str(CURRENT_RUN),
        "total_rows": 53209,
        "train_rows": 42567,
        "val_rows": 5320,
        "test_rows": 5322,
    }
    
    with open(CURRENT_RUN / "run_info.json", "w") as f:
        json.dump(run_info, f, indent=2)
    
    print(f"\n✅ Evaluation complete!")
    print(f"📁 All results saved to: {CURRENT_RUN}")
    print(f"📊 Open {CURRENT_RUN}/report.html in your browser to view the report")

if __name__ == "__main__":
    main()
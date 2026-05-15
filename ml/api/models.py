from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import pandas as pd


STRUCT_COLS = [
    "root_outdeg", "num_nodes", "num_edges", "tree_depth",
    "max_breadth", "leaf_nodes", "leaf_ratio", "avg_outdeg",
    "branching_factor",
]

ENHANCED_COLS = [
    "text_length", "has_url", "has_question", "has_exclamation",
    "caps_ratio", "has_share_phrase", "has_urgency_phrase",
    "has_numbers", "sentiment_score", "readability_score",
]


def norm_text(text: str) -> str:
    return (text or "").strip()


def make_feature_frame(
    text: str,
    struct: Optional[Dict[str, float]] = None,
    extra: Optional[Dict[str, float]] = None,
) -> pd.DataFrame:
    row: Dict[str, Any] = {"source_text": text}

    struct = struct or {}
    defaults = {
        "root_outdeg": 0.0,
        "num_nodes": 1.0,
        "num_edges": 0.0,
        "tree_depth": 0.0,
        "max_breadth": 1.0,
        "leaf_nodes": 1.0,
        "leaf_ratio": 1.0,
        "avg_outdeg": 0.0,
        "branching_factor": 0.0,
    }
    for c in STRUCT_COLS:
        row[c] = float(struct.get(c, defaults.get(c, 0.0)))

    extra = extra or {}
    for c in ENHANCED_COLS:
        row[c] = float(extra.get(c, 0.0))

    return pd.DataFrame([row])


def predict_probs_unified(
    model: Any,
    text: str,
    struct: Optional[Dict[str, float]] = None,
    extra: Optional[Dict[str, float]] = None,
) -> Dict[str, float]:
    X = make_feature_frame(text, struct=struct, extra=extra)
    proba = model.predict_proba(X)[0]
    return {"prob_neg": float(proba[0]), "prob_pos": float(proba[1])}


def risk_band(prob_pos: float) -> str:
    """
    Keep backend thresholds aligned with the frontend:
      0.00 - 0.14 -> LOW
      0.15 - 0.44 -> MEDIUM
      0.45+       -> HIGH
    """
    if prob_pos >= 0.45:
        return "HIGH"
    if prob_pos >= 0.15:
        return "MEDIUM"
    return "LOW"


def control_action(band: str) -> str:
    b = (band or "").upper()
    if b == "HIGH":
        return (
            "High-risk signal. Do not share until the claim has been checked against trusted primary sources."
        )
    if b == "MEDIUM":
        return (
            "Medium-risk signal. Verify key claims using trusted sources before sharing."
        )
    return (
        "Low-risk signal. Sharing risk appears lower, but still verify if the claim is high-impact or time-sensitive."
    )


def load_model_with_threshold(
    model_path: Path,
    threshold_path: Path,
    default_threshold: float,
) -> Tuple[Any, float]:
    import joblib

    model = joblib.load(model_path)
    threshold = float(default_threshold)

    try:
        if threshold_path.exists():
            data = json.loads(threshold_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                threshold = float(data.get("best_threshold", threshold))
    except Exception:
        pass

    return model, threshold


def log_event(
    request_id: str,
    endpoint: str,
    event_type: str,
    model_name: str,
    input_payload: Dict[str, Any],
    output_payload: Dict[str, Any],
    path: Path,
) -> None:
    import datetime

    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "ts": datetime.datetime.utcnow().isoformat() + "Z",
        "request_id": request_id,
        "endpoint": endpoint,
        "event_type": event_type,
        "model": model_name,
        "input": input_payload,
        "output": output_payload,
    }
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def compute_trends(events_log: Path, limit: int = 20, window: int = 2000) -> Dict[str, Any]:
    import re
    from collections import Counter

    if not events_log.exists():
        return {"terms": [], "window": window, "total_events": 0}

    lines = events_log.read_text(encoding="utf-8", errors="ignore").splitlines()
    recent = lines[-window:] if len(lines) > window else lines

    counter = Counter()
    total = 0
    for line in recent:
        try:
            obj = json.loads(line)
            text = (obj.get("input", {}) or {}).get("text", "") or ""
            text = text.lower()
            tokens = re.findall(r"[a-z]{3,}", text)
            counter.update(tokens)
            total += 1
        except Exception:
            continue

    top = [{"term": t, "count": c} for t, c in counter.most_common(limit)]
    return {"terms": top, "window": window, "total_events": total}
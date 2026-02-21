# ml/api/predict_service.py
from __future__ import annotations

import traceback
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from .models import (
    norm_text,
    predict_probs_unified,
    risk_band,
    control_action,
)
from .analysis import (
    build_trigger_breakdown,
    build_propagation_dynamics,
    build_susceptibility_logic,
    build_algorithmic_advantage,
)
from .stance_detector import detect_stance, adjust_risk_by_stance
from .explanations import generate_analyst, generate_explanation


# ============================================================================
# Enhanced early-warning features 
# ============================================================================
def extract_enhanced_features(text: str) -> Dict[str, float]:
    import re

    t = text or ""
    text_lower = t.lower()

    features = {
        "text_length": float(len(t)),
        "has_url": 1.0 if re.search(r"http[s]?://|www\.", text_lower) else 0.0,
        "has_question": 1.0 if "?" in t else 0.0,
        "has_exclamation": 1.0 if "!" in t else 0.0,
        "has_numbers": 1.0 if re.search(r"\d+", t) else 0.0,
    }

    share_words = ["share", "forward", "spread", "retweet", "pass", "tell everyone"]
    share_count = sum(1 for word in share_words if word in text_lower)
    features["share_prompts"] = min(share_count / 3.0, 1.0)

    urgency_words = ["breaking", "urgent", "just in", "now", "immediately", "right now", "alert"]
    urgency_count = sum(1 for word in urgency_words if word in text_lower)
    features["urgency_score"] = min(urgency_count / 3.0, 1.0)

    conspiracy_phrases = ["cover up", "they don't want", "hidden truth", "secret", "what they won't tell"]
    conspiracy_count = sum(1 for phrase in conspiracy_phrases if phrase in text_lower)
    features["conspiracy_score"] = min(conspiracy_count / 2.0, 1.0)

    excl_count = t.count("!")
    ques_count = t.count("?")
    features["emotional_intensity"] = min((excl_count + ques_count) / 5.0, 1.0)

    if len(t) > 0:
        caps_count = sum(1 for c in t if c.isupper())
        features["caps_ratio"] = float(caps_count / len(t))
        features["caps_emphasis"] = min(features["caps_ratio"] * 2, 1.0)
    else:
        features["caps_ratio"] = 0.0
        features["caps_emphasis"] = 0.0

    virality_components = [
        features["share_prompts"] * 0.3,
        features["urgency_score"] * 0.25,
        features["conspiracy_score"] * 0.2,
        features["emotional_intensity"] * 0.15,
        features["caps_emphasis"] * 0.1,
    ]
    features["virality_score"] = sum(virality_components)
    return features


def predict_enhanced_early(model: Any, text: str) -> Dict[str, float]:
    features = extract_enhanced_features(text)

    model_features = {
        "source_text": text,
        "root_outdeg": 0.0,
        "num_nodes": 1.0,
        "num_edges": 0.0,
        "tree_depth": 0.0,
        "max_breadth": 1.0,
        "leaf_nodes": 1.0,
        "leaf_ratio": 1.0,
        "avg_outdeg": 0.0,
        "branching_factor": 0.0,
        "text_length": features.get("text_length", 0),
        "has_url": features.get("has_url", 0),
        "has_question": features.get("has_question", 0),
        "has_exclamation": features.get("has_exclamation", 0),
        "has_numbers": features.get("has_numbers", 0),
        "caps_ratio": features.get("caps_ratio", 0),
        "has_share_phrase": features.get("share_prompts", 0),
        "has_urgency_phrase": features.get("urgency_score", 0),
        "sentiment_score": features.get("emotional_intensity", 0),
        "readability_score": 0.5,
    }

    X = pd.DataFrame([model_features])

    try:
        proba = model.predict_proba(X)[0]
        model_prob = float(proba[1])
    except Exception as e:
        print(f"⚠️ Early model prediction failed: {e} — using fallback")
        model_prob = 0.3

    virality_score = features.get("virality_score", 0)
    enhanced_prob = (model_prob * 0.7) + (virality_score * 0.3)

    return {
        "probability": float(enhanced_prob),
        "model_prob": float(model_prob),
        "virality_score": float(virality_score),
        "share_prompts": float(features.get("share_prompts", 0)),
        "urgency_score": float(features.get("urgency_score", 0)),
    }


# ============================================================================
# Ensemble + verdicts
# ============================================================================
def ensemble_prediction(
    unified_prob: float,
    enhanced_prob: Optional[float],
    legacy_prob: Optional[float],
    bert_prob: Optional[float] = None,
) -> Dict[str, Any]:
    weights = {
        "unified": 0.20,
        "enhanced": 0.20,
        "legacy": 0.10,
        "bert": 0.50,
    }

    present = {"unified": unified_prob}
    if enhanced_prob is not None:
        present["enhanced"] = enhanced_prob
    if legacy_prob is not None:
        present["legacy"] = legacy_prob
    if bert_prob is not None:
        present["bert"] = bert_prob

    total_w = sum(weights[k] for k in present.keys())
    norm_w = {k: weights[k] / total_w for k in present.keys()}

    ensemble_prob = 0.0
    for k, v in present.items():
        ensemble_prob += float(v) * norm_w[k]

    return {
        "ensemble_probability": float(ensemble_prob),
        "unified_probability": float(unified_prob),
        "enhanced_probability": float(enhanced_prob) if enhanced_prob is not None else None,
        "legacy_probability": float(legacy_prob) if legacy_prob is not None else None,
        "bert_probability": float(bert_prob) if bert_prob is not None else None,
        "weights": norm_w,
    }


def determine_action_verdict(prob_pos: float, text: str) -> Tuple[str, str, Optional[str]]:
    text_lower = (text or "").lower()

    if any(platform in text_lower for platform in ["facebook", "instagram", "whatsapp", "twitter", "meta"]) and \
       any(word in text_lower for word in ["$", "fee", "charge", "payment", "5.99", "9.99", "month"]) and \
       any(word in text_lower for word in ["share", "forward", "copy", "paste", "opt out", "pass"]):
        return (
            "VERIFY_REQUIRED",
            "This looks like a common viral hoax where scammers claim platforms will start charging fees.",
            "⚠️ Pattern: Share-to-opt-out hoax",
        )

    if any(celebrity in text_lower for celebrity in ["taylor swift", "beyoncé", "rihanna", "justin bieber", "drake"]) and \
       any(word in text_lower for word in ["died", "dead", "rip", "passed away", "killed", "crash"]):
        return (
            "LIKELY_MISINFORMATION",
            "Celebrity death claims like this resurface periodically and are almost always false.",
            "⚠️ Pattern: Celebrity death hoax",
        )

    if any(word in text_lower for word in ["vaccine", "vax", "shot"]) and \
       any(word in text_lower for word in ["microchip", "tracking", "5g", "chip", "track"]):
        return (
            "LIKELY_MISINFORMATION",
            "This is a known conspiracy theory that has been debunked by health authorities worldwide.",
            "⚠️ Pattern: Vaccine conspiracy",
        )

    if any(word in text_lower for word in ["urgent", "important", "warning", "alert"]) and \
       any(word in text_lower for word in ["$", "money", "bank", "account", "pay", "fee"]) and \
       any(word in text_lower for word in ["share", "forward", "tell", "spread"]):
        return (
            "VERIFY_REQUIRED",
            "Urgent financial requests that ask you to share are often scams.",
            "⚠️ Pattern: Urgent financial scam",
        )

    if prob_pos >= 0.60:
        return ("LIKELY_MISINFORMATION", "The pattern of this content strongly suggests it's false.", None)
    if prob_pos >= 0.30:
        return ("VERIFY_REQUIRED", "This content shows some suspicious patterns — better to check before sharing.", None)
    return ("SAFE_TO_SHARE", "This content appears to be legitimate based on our analysis.", None)


def calculate_tactics_score(triggers: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not triggers:
        return {"score": 0.0, "band": "LOW", "intensity": 0.0, "triggers": []}

    avg_score = sum(t.get("score", 0.0) for t in triggers) / max(1, len(triggers))

    if avg_score >= 0.6:
        band = "HIGH"
    elif avg_score >= 0.3:
        band = "MEDIUM"
    else:
        band = "LOW"

    mx = max(t.get("score", 0.0) for t in triggers)
    mn = min(t.get("score", 0.0) for t in triggers)
    trigger_consistency = 1.0 - (mx - mn)
    intensity = min(1.0, (len(triggers) / 5.0) * trigger_consistency)

    return {"score": float(avg_score), "band": band, "intensity": float(intensity), "triggers": triggers[:5]}


def generate_user_friendly_explanation(
    text: str,
    action_verdict: str,
    action_reason: str,
    prob_pos: float,
    prob_neg: float,
    early_prob: Optional[float],
    signals: Dict[str, Any],
    guidance: str,
    triggers: List[Dict[str, Any]],
    adjusted_prob: Optional[float] = None,
    stance: str = "neutral",
    misinformation_band: str = "LOW",
    tactics_band: str = "LOW",
    key_phrases: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Generate user-friendly explanation - now uses the detailed explanation from explanations.py
    """
    # Use the detailed explanation generator
    detailed_exp = generate_explanation(
        text=text,
        verdict=action_verdict,
        risk_band=signals.get("risk_band", "MEDIUM"),
        prob_pos=prob_pos,
        prob_neg=prob_neg,
        early_prob=early_prob,
        signals=signals,
        guidance=guidance,
        stance=stance,
        triggers=triggers,
        key_phrases=key_phrases,
    )
    
    return {
        "user_summary": detailed_exp.get("user_summary", ""),
        "user_reasons": detailed_exp.get("user_reasons", []),
        "user_guidance": detailed_exp.get("user_guidance", guidance),
        "final_explanation": detailed_exp.get("final_explanation", action_reason),
        "signals": signals,
        "key_phrases": key_phrases or [],
    }


# ============================================================================
# Main pipeline function (called by FastAPI route)
# ============================================================================
def run_predict_auto(
    *,
    text: str,
    request_id: str,
    endpoint: str,
    unified_model: Any,
    health_model: Optional[Any],
    enhanced_early_model: Optional[Any],
    legacy_early_model: Optional[Any],
    bert_classifier: Optional[Any],
) -> Dict[str, Any]:
    """
    Returns a dict matching AutoPredictResponse schema.
    Raises exceptions to be handled by main.py route.
    """
    text = norm_text(text)
    if not text:
        raise ValueError("Missing or empty 'text'")

    # Unified model
    u = predict_probs_unified(unified_model, text)
    prob_unified = float(u["prob_pos"])

    # Health model (optional)
    prob_health = None
    if health_model is not None:
        try:
            h = predict_probs_unified(health_model, text)
            prob_health = float(h["prob_pos"])
        except Exception as e:
            print(f"⚠️ Health model failed: {e}")

    # Early enhanced model (optional)
    prob_enhanced = None
    early_dict = None
    if enhanced_early_model is not None:
        try:
            early_dict = predict_enhanced_early(enhanced_early_model, text)
            prob_enhanced = float(early_dict["probability"])
        except Exception as e:
            print(f"⚠️ Early model failed: {e}")

    # Legacy early model (optional)
    prob_legacy = None
    if legacy_early_model is not None:
        try:
            legacy_pred = predict_probs_unified(legacy_early_model, text)
            prob_legacy = float(legacy_pred["prob_pos"])
        except Exception as e:
            print(f"⚠️ Legacy model failed: {e}")

    # Stance + (optional) “bert_classifier” block (your current system)
    stance_data = detect_stance(text)
    stance = stance_data["stance"]

    bert_risk = None
    key_phrases: List[Dict[str, Any]] = []
    if bert_classifier is not None:
        try:
            br = bert_classifier.classify(text)  # your existing interface
            bert_risk = float(br.get("risk_score", 0.5))
            stance = br.get("stance", stance)
            key_phrases = br.get("key_phrases", []) or []
        except Exception as e:
            print(f"⚠️ bert_classifier failed: {e}")
            bert_risk = None

    # Ensemble
    ens = ensemble_prediction(
        unified_prob=prob_unified,
        enhanced_prob=prob_enhanced,
        legacy_prob=prob_legacy,
        bert_prob=bert_risk,
    )
    ensemble_prob = float(ens["ensemble_probability"])
    confidence = max(ensemble_prob, 1.0 - ensemble_prob)

    # If no bert_classifier, adjust risk by stance (your existing design)
    if bert_classifier is None:
        ensemble_prob = float(adjust_risk_by_stance(ensemble_prob, stance_data))

    # Backward-compatible risk band
    band = risk_band(ensemble_prob)

    # Action verdict
    action_verdict, action_reason, override_note = determine_action_verdict(ensemble_prob, text)

    # Triggers
    raw_triggers = build_trigger_breakdown(text, stance=stance)
    triggers = raw_triggers[:5]

    # Early block (schema EarlyBlock)
    early_block = None
    if early_dict is not None:
        early_block = {
            "model_used": "enhanced_early",
            "prob_pos": float(early_dict["probability"]),
            "risk_band": risk_band(float(early_dict["probability"])),
            "virality_score": float(early_dict.get("virality_score", 0.0)),
        }

    # “Two score” split (schema)
    misinformation_band = "HIGH" if ensemble_prob >= 0.45 else ("MEDIUM" if ensemble_prob >= 0.15 else "LOW")
    tactics_data = calculate_tactics_score(triggers)

    guidance = control_action(band)

    signals = {
        "endpoint": endpoint,
        "prob_unified": prob_unified,
        "prob_health": prob_health,
        "prob_enhanced": prob_enhanced,
        "prob_legacy": prob_legacy,
        "bert_risk": bert_risk,
        "ensemble_prob": ensemble_prob,
        "confidence": confidence,
        "risk_band": band,
        "stance": stance,
        "misinformation_band": misinformation_band,
        "tactics_band": tactics_data["band"],
        "tactics_intensity": tactics_data["intensity"],
    }

    exp = generate_user_friendly_explanation(
        text=text,
        action_verdict=action_verdict,
        action_reason=action_reason,
        prob_pos=ensemble_prob,
        prob_neg=1.0 - ensemble_prob,
        early_prob=(float(early_dict["probability"]) if early_dict else None),
        signals=signals,
        guidance=guidance,
        triggers=triggers,
        adjusted_prob=ensemble_prob,
        stance=stance,
        misinformation_band=misinformation_band,
        tactics_band=tactics_data["band"],
        key_phrases=key_phrases,
    )

    # Analyst block (LLM preferred, rule-based fallback)
    try:
        analyst_data = generate_analyst(
            text=text,
            verdict=action_verdict,
            risk_band=band,
            prob_pos=ensemble_prob,
            stance=stance,
        )
    except Exception as e:
        print(f"⚠️ Analyst generation failed, using fallback: {e}")
        analyst_data = {
            "triggers": triggers,
            "propagation_dynamics": build_propagation_dynamics(band, stance),
            "human_susceptibility_logic": build_susceptibility_logic(text, stance),
            "algorithmic_advantage": build_algorithmic_advantage(text, stance),
            "note": "Analysis based on linguistic patterns and stance cues.",
        }

    model_breakdown = {
        "unified": prob_unified,
        "enhanced": prob_enhanced,
        "legacy": prob_legacy,
        "ensemble": ensemble_prob,
    }

    misinformation_score = {
        "band": misinformation_band,
        "probability": float(ensemble_prob),
        "raw_probability": float(ensemble_prob),
        "explanation": f"Stance: {stance}.",
        "stance": stance,  # must match schema: debunking/warning/neutral/spreading
    }

    tactics_score = {
        "band": tactics_data["band"],
        "intensity": float(tactics_data["intensity"]),
        "detected_triggers": triggers,
        "overall_assessment": (
            f"Detected {len(triggers)} engagement cues. "
            f"Average intensity approx. {tactics_data['score']:.0%}."
        ),
    }

    resp = {
        "request_id": request_id,
        "misinformation": misinformation_score,
        "manipulation_tactics": tactics_score,
        "action_verdict": action_verdict,
        "action_reason": action_reason,
        "override_note": override_note,
        "confidence": float(confidence),
        "risk_band": band,
        "misinfo_probability": float(ensemble_prob),
        "model_breakdown": model_breakdown,
        "triggers": triggers,
        "early": early_block,
        "explanation": exp,
        "analyst": {
            "triggers": analyst_data.get("triggers", []),
            "propagation_dynamics": analyst_data.get("propagation_dynamics", {}),
            "human_susceptibility_logic": analyst_data.get("human_susceptibility_logic", ""),
            "algorithmic_advantage": analyst_data.get("algorithmic_advantage", ""),
            "note": analyst_data.get("note", ""),
        },
        "input_type": "text",
        "extracted_text": None,
        "filename": None,
    }

    return resp
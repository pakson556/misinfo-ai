from __future__ import annotations

from typing import Any, Dict, List, Optional

from .analysis import (
    build_algorithmic_advantage,
    build_propagation_dynamics,
    build_susceptibility_logic,
    build_trigger_breakdown,
)
from .explanations import generate_analyst, generate_explanation
from .internet_verifier import verify_text_on_web
from .models import (
    control_action,
    make_feature_frame,
    norm_text,
    predict_probs_unified,
    risk_band,
)
from .stance_detector import adjust_risk_by_stance, detect_stance


def extract_enhanced_features(text: str) -> Dict[str, float]:
    import re

    t = text or ""
    text_lower = t.lower()

    sentence_count = max(1, len(re.findall(r"[.!?]+", t)) or 1)
    word_count = max(1, len(re.findall(r"\b\w+\b", t)))

    share_phrases = [
        "share",
        "share this",
        "forward this",
        "retweet",
        "spread this",
        "tell everyone",
        "pass this on",
        "do your own research",
    ]
    urgency_phrases = [
        "breaking",
        "urgent",
        "right now",
        "immediately",
        "act now",
        "just in",
        "alert",
    ]

    caps_chars = sum(1 for c in t if c.isupper())
    alpha_chars = sum(1 for c in t if c.isalpha())
    caps_ratio = float(caps_chars / alpha_chars) if alpha_chars > 0 else 0.0

    return {
        "text_length": float(len(t)),
        "has_url": 1.0 if re.search(r"http[s]?://|www\.", text_lower) else 0.0,
        "has_question": 1.0 if "?" in t else 0.0,
        "has_exclamation": 1.0 if "!" in t else 0.0,
        "caps_ratio": caps_ratio,
        "has_share_phrase": 1.0 if any(p in text_lower for p in share_phrases) else 0.0,
        "has_urgency_phrase": 1.0 if any(p in text_lower for p in urgency_phrases) else 0.0,
        "has_numbers": 1.0 if re.search(r"\d+", t) else 0.0,
        "sentiment_score": 0.0,
        "readability_score": float(word_count / sentence_count),
    }


def predict_enhanced_early(model: Any, text: str) -> Dict[str, float]:
    """
    Use the same feature-frame structure expected by the sklearn pipeline.
    """
    extra = extract_enhanced_features(text)
    x = make_feature_frame(text=text, struct=None, extra=extra)
    prob = float(model.predict_proba(x)[0][1])

    virality_inputs = [
        extra.get("has_share_phrase", 0.0),
        extra.get("has_urgency_phrase", 0.0),
        extra.get("has_exclamation", 0.0),
        extra.get("has_numbers", 0.0),
    ]
    virality_score = min(1.0, sum(virality_inputs) / 4.0)

    return {
        "probability": prob,
        "virality_score": float(virality_score),
    }


def ensemble_prediction(
    *,
    unified_prob: float,
    enhanced_prob: Optional[float],
    legacy_prob: Optional[float],
    bert_prob: Optional[float],
) -> Dict[str, float]:
    probs = [float(unified_prob)]
    weights = [0.50]

    if enhanced_prob is not None:
        probs.append(float(enhanced_prob))
        weights.append(0.20)

    if legacy_prob is not None:
        probs.append(float(legacy_prob))
        weights.append(0.15)

    if bert_prob is not None:
        probs.append(float(bert_prob))
        weights.append(0.15)

    total_weight = sum(weights) if weights else 1.0
    ensemble = sum(p * w for p, w in zip(probs, weights)) / total_weight

    return {"ensemble_probability": float(max(0.0, min(1.0, ensemble)))}


def compute_model_confidence(
    *,
    ensemble_prob: float,
    model_probs: List[Optional[float]],
    internet_verification: Optional[Dict[str, Any]] = None,
) -> float:
    """
    Confidence is separate from misinformation likelihood.

    It combines:
    1. Distance from the decision boundary (0.5)
    2. Agreement between available models
    3. Optional internet verification confidence boost
    """
    p = float(max(0.0, min(1.0, ensemble_prob)))

    # Near 0.5 => uncertain, near 0 or 1 => more certain
    distance_conf = abs(p - 0.5) * 2.0  # 0..1

    usable = [float(x) for x in model_probs if x is not None]
    if len(usable) >= 2:
        spread = max(usable) - min(usable)  # 0 means strong agreement
        agreement_conf = max(0.0, 1.0 - spread)
    else:
        agreement_conf = distance_conf

    confidence = (0.65 * distance_conf) + (0.35 * agreement_conf)

    if internet_verification and internet_verification.get("performed"):
        web_conf = float(internet_verification.get("overall_confidence", 0.0))
        web_verdict = str(
            internet_verification.get("overall_verdict", "UNVERIFIED")
        ).upper()

        if web_verdict in {"LIKELY_TRUE", "LIKELY_FALSE"}:
            confidence = (0.80 * confidence) + (0.20 * web_conf)
        elif web_verdict == "MIXED":
            confidence = min(confidence, 0.65)

    return float(max(0.05, min(0.99, confidence)))


def determine_action_verdict(
    prob: float,
    text: str,
    internet_verification: Optional[Dict[str, Any]] = None,
) -> tuple[str, str, Optional[str]]:
    lowered = (text or "").lower()

    if internet_verification and internet_verification.get("performed"):
        overall = internet_verification.get("overall_verdict")
        conf = float(internet_verification.get("overall_confidence", 0.0))

        if overall == "LIKELY_TRUE" and conf >= 0.75 and prob < 0.15:
            return (
                "SAFE_TO_SHARE",
                "Trusted evidence strongly supports the claims in this content.",
                "Strong external support",
            )

        if overall == "LIKELY_FALSE" and conf >= 0.65:
            return (
                "LIKELY_MISINFORMATION",
                "Trusted evidence strongly contradicts the claims in this content.",
                "Strong external contradiction",
            )

    if prob >= 0.45:
        return (
            "LIKELY_MISINFORMATION",
            "The system detected strong misinformation-related patterns. This content should not be trusted without independent verification.",
            None,
        )

    if prob >= 0.15:
        return (
            "VERIFY_REQUIRED",
            "The system found some suspicious or uncertain signals. This content should be checked against reliable sources before sharing.",
            None,
        )

    if any(x in lowered for x in ["breaking", "urgent", "share this"]):
        return (
            "VERIFY_REQUIRED",
            "Although the model score is low, the wording still suggests caution. Verify before sharing.",
            "Low model risk but cautionary wording present.",
        )

    return (
        "SAFE_TO_SHARE",
        "The content does not show strong misinformation signals in the model analysis.",
        None,
    )


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

    return {
        "score": float(avg_score),
        "band": band,
        "intensity": float(intensity),
        "triggers": triggers[:5],
    }


def _guidance_from_band_and_verdict(band: str, action_verdict: str) -> str:
    b = str(band or "MEDIUM").upper()
    verdict = str(action_verdict or "").upper()

    if b == "HIGH" or verdict in {"LIKELY_MISINFORMATION", "DO_NOT_SHARE"}:
        return "High-risk signal. Do not share until the claim has been checked against trusted primary sources."

    if b == "MEDIUM" or verdict == "VERIFY_REQUIRED":
        return "Medium-risk signal. Verify key claims using trusted sources before sharing."

    return "Low-risk signal. Sharing risk appears lower, but still verify if the claim is high-impact or time-sensitive."


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
        key_phrases=key_phrases or [],
    )

    return {
        "user_summary": detailed_exp.get("user_summary", ""),
        "user_reasons": detailed_exp.get("user_reasons", []),
        "user_guidance": detailed_exp.get("user_guidance", guidance),
        "final_explanation": detailed_exp.get("final_explanation", action_reason),
        "signals": signals,
        "key_phrases": key_phrases or [],
    }


def _apply_internet_adjustment(
    ensemble_prob: float,
    internet_verification: Optional[Dict[str, Any]],
) -> float:
    """
    Smoothly adjust the raw ensemble probability using internet verification.

    This avoids hard-coded-feeling outputs such as many cases always becoming
    8% or 18%. Instead, the final score moves gradually based on:
    - the raw model probability
    - the verification verdict
    - the verification confidence
    """
    if not internet_verification or not internet_verification.get("performed"):
        return ensemble_prob

    overall = internet_verification.get("overall_verdict", "UNVERIFIED")
    conf = float(internet_verification.get("overall_confidence", 0.0))
    adjusted = float(ensemble_prob)

    if overall == "LIKELY_TRUE":
        adjusted = ensemble_prob * (1.0 - 0.70 * conf)

    elif overall == "LEANING_TRUE":
        adjusted = ensemble_prob * (1.0 - 0.35 * conf)

    elif overall == "LIKELY_FALSE":
        adjusted = ensemble_prob + (1.0 - ensemble_prob) * (0.70 * conf)

    elif overall == "LEANING_FALSE":
        adjusted = ensemble_prob + (1.0 - ensemble_prob) * (0.35 * conf)

    elif overall == "MIXED":
        adjusted = 0.7 * ensemble_prob + 0.3 * 0.25

    return float(max(0.01, min(0.99, adjusted)))


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
    enable_internet: bool = True,
) -> Dict[str, Any]:
    text = norm_text(text)
    if not text:
        raise ValueError("Missing or empty 'text'")

    u = predict_probs_unified(unified_model, text)
    prob_unified = float(u["prob_pos"])

    prob_health = None
    if health_model is not None:
        try:
            h = predict_probs_unified(health_model, text)
            prob_health = float(h["prob_pos"])
        except Exception as e:
            print(f"⚠️ Health model failed: {e}")

    prob_enhanced = None
    early_dict = None
    if enhanced_early_model is not None:
        try:
            early_dict = predict_enhanced_early(enhanced_early_model, text)
            prob_enhanced = float(early_dict["probability"])
        except Exception as e:
            print(f"⚠️ Early model failed: {e}")

    prob_legacy = None
    if legacy_early_model is not None:
        try:
            legacy_pred = predict_probs_unified(legacy_early_model, text)
            prob_legacy = float(legacy_pred["prob_pos"])
        except Exception as e:
            print(f"⚠️ Legacy model failed: {e}")

    stance_data = detect_stance(text)
    stance = stance_data["stance"]

    bert_risk = None
    key_phrases: List[Dict[str, Any]] = []
    if bert_classifier is not None:
        try:
            br = bert_classifier.classify(text)
            bert_risk = float(br.get("risk_score", 0.5))
            stance = br.get("stance", stance)
            key_phrases = br.get("key_phrases", []) or []
        except Exception as e:
            print(f"⚠️ bert_classifier failed: {e}")
            bert_risk = None

    ens = ensemble_prediction(
        unified_prob=prob_unified,
        enhanced_prob=prob_enhanced,
        legacy_prob=prob_legacy,
        bert_prob=bert_risk,
    )
    ensemble_prob_raw = float(ens["ensemble_probability"])

    if bert_classifier is None:
        ensemble_prob_raw = float(adjust_risk_by_stance(ensemble_prob_raw, stance_data))

    internet_verification = {
        "enabled": bool(enable_internet),
        "performed": False,
        "overall_verdict": "UNVERIFIED",
        "overall_confidence": 0.0,
        "claims": [],
        "sources": [],
        "summary_note": "Internet verification disabled.",
        "error": None,
    }

    if enable_internet:
        try:
            internet_verification = verify_text_on_web(text)
        except Exception as e:
            print(f"⚠️ Internet verification failed: {e}")
            internet_verification = {
                "enabled": True,
                "performed": False,
                "overall_verdict": "UNVERIFIED",
                "overall_confidence": 0.0,
                "claims": [],
                "sources": [],
                "summary_note": "Internet verification failed.",
                "error": str(e),
            }

    ensemble_prob = _apply_internet_adjustment(ensemble_prob_raw, internet_verification)

    confidence = compute_model_confidence(
        ensemble_prob=ensemble_prob,
        model_probs=[
            prob_unified,
            prob_health,
            prob_enhanced,
            prob_legacy,
            bert_risk,
        ],
        internet_verification=internet_verification,
    )

    band = risk_band(ensemble_prob)

    action_verdict, action_reason, override_note = determine_action_verdict(
        ensemble_prob,
        text,
        internet_verification,
    )

    raw_triggers = build_trigger_breakdown(text, stance=stance)
    triggers = raw_triggers[:5]

    early_block = None
    if early_dict is not None:
        early_block = {
            "model_used": "enhanced_early",
            "prob_pos": float(early_dict["probability"]),
            "risk_band": risk_band(float(early_dict["probability"])),
            "virality_score": float(early_dict.get("virality_score", 0.0)),
        }

    misinformation_band = "HIGH" if ensemble_prob >= 0.45 else ("MEDIUM" if ensemble_prob >= 0.15 else "LOW")
    tactics_data = calculate_tactics_score(triggers)
    guidance = _guidance_from_band_and_verdict(band, action_verdict) or control_action(band)

    signals = {
        "endpoint": endpoint,
        "prob_unified": prob_unified,
        "prob_health": prob_health,
        "prob_enhanced": prob_enhanced,
        "prob_legacy": prob_legacy,
        "bert_risk": bert_risk,
        "ensemble_prob_raw": ensemble_prob_raw,
        "ensemble_prob_final": ensemble_prob,
        "confidence": confidence,
        "risk_band": band,
        "stance": stance,
        "misinformation_band": misinformation_band,
        "tactics_band": tactics_data["band"],
        "tactics_intensity": tactics_data["intensity"],
        "internet_enabled": enable_internet,
        "internet_overall_verdict": internet_verification.get("overall_verdict"),
        "internet_overall_confidence": internet_verification.get("overall_confidence"),
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

    if internet_verification.get("enabled"):
        web_note = internet_verification.get("summary_note", "")
        if web_note:
            exp["user_reasons"] = list(exp.get("user_reasons", [])) + [f"Internet verification: {web_note}"]

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
            "note": "Analysis based on linguistic patterns, stance cues, and optional web evidence.",
        }

    model_breakdown = {
        "unified": prob_unified,
        "health": prob_health,
        "enhanced": prob_enhanced,
        "legacy": prob_legacy,
        "bert": bert_risk,
        "ensemble": ensemble_prob,
    }

    misinformation_explanation = f"Stance: {stance}."
    if internet_verification.get("performed"):
        misinformation_explanation += (
            f" Internet verdict: {internet_verification.get('overall_verdict', 'UNVERIFIED')} "
            f"({float(internet_verification.get('overall_confidence', 0.0)):.0%} confidence)."
        )

    misinformation_score = {
        "band": misinformation_band,
        "probability": float(ensemble_prob),
        "raw_probability": float(ensemble_prob_raw),
        "explanation": misinformation_explanation,
        "stance": stance,
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

    return {
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
        "internet_verification": internet_verification,
        "input_type": "text",
        "extracted_text": None,
        "filename": None,
    }
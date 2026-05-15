#!/usr/bin/env python3
"""
BERT / fallback classifier for misinformation detection.

Important:
- This file NEVER returns stance="credible"
- Allowed stance values are only:
  - debunking
  - warning
  - neutral
  - spreading

This fixes the FastAPI ResponseValidationError caused by:
misinformation.stance = "credible"
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, Optional

# Optional transformer stack
try:
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    TRANSFORMERS_AVAILABLE = True
except Exception:
    torch = None
    AutoModelForSequenceClassification = None
    AutoTokenizer = None
    TRANSFORMERS_AVAILABLE = False


def _clip01(value: float) -> float:
    try:
        v = float(value)
    except Exception:
        return 0.0
    if v < 0.0:
        return 0.0
    if v > 1.0:
        return 1.0
    return v


def _normalise_stance(value: Optional[str]) -> str:
    """
    Force stance into the exact schema-safe literals.
    """
    if not value:
        return "neutral"

    v = str(value).strip().lower()

    mapping = {
        "credible": "neutral",
        "safe": "neutral",
        "true": "neutral",
        "real": "neutral",
        "factual": "neutral",
        "neutral": "neutral",
        "debunking": "debunking",
        "warning": "warning",
        "spreading": "spreading",
    }
    return mapping.get(v, "neutral")


class BertMisinformationClassifier:
    """
    Loads a transformer model when available.
    Falls back to rule-based classification when transformers/torch are not installed.
    """

    def __init__(
        self,
        model_name: Optional[str] = None,
        local_model_dir: Optional[str] = None,
    ) -> None:
        self.model_name = model_name or os.getenv(
            "BERT_MODEL_NAME", "distilbert-base-uncased-finetuned-sst-2-english"
        )
        self.local_model_dir = local_model_dir or os.getenv("BERT_LOCAL_MODEL_DIR")
        self.available = False
        self.mode = "fallback"
        self.tokenizer = None
        self.model = None

        if TRANSFORMERS_AVAILABLE:
            self._try_load_transformer()
        else:
            print("⚠️ Transformers/torch not available. BERT classifier will use fallback mode.")

        if not self.available:
            print("⚠️ BERT classifier running in fallback mode (rule-based)")

    def _try_load_transformer(self) -> None:
        """
        Try to load a transformer classifier. If anything fails, stay in fallback mode.
        """
        try:
            load_target = self.local_model_dir or self.model_name
            self.tokenizer = AutoTokenizer.from_pretrained(load_target)
            self.model = AutoModelForSequenceClassification.from_pretrained(load_target)
            self.model.eval()
            self.available = True
            self.mode = "transformer"
            print(f"✅ Loaded transformer classifier: {load_target}")
        except Exception as exc:
            self.available = False
            self.mode = "fallback"
            self.tokenizer = None
            self.model = None
            print(f"⚠️ Failed to load transformer classifier. Using fallback mode: {exc}")

    def predict(self, text: str) -> Dict[str, Any]:
        """
        Main public method.
        """
        return self.classify(text)

    def __call__(self, text: str) -> Dict[str, Any]:
        return self.classify(text)

    def classify(self, text: str) -> Dict[str, Any]:
        """
        Returns a stable result dictionary.
        """
        clean_text = (text or "").strip()

        if not clean_text:
            return {
                "label": "LOW_RISK",
                "stance": "neutral",
                "confidence": 0.55,
                "risk_score": 0.05,
                "probability": 0.05,
                "explanation": "No text provided.",
                "model_name": "fallback-empty",
                "mode": self.mode,
            }

        if self.available and self.tokenizer is not None and self.model is not None:
            try:
                return self._predict_transformer(clean_text)
            except Exception as exc:
                print(f"⚠️ Transformer inference failed. Falling back to rules: {exc}")

        return self._predict_fallback(clean_text)

    def _predict_transformer(self, text: str) -> Dict[str, Any]:
        """
        Transformer prediction path.
        This remains conservative and still outputs schema-safe stance values.
        """
        assert self.tokenizer is not None
        assert self.model is not None
        assert torch is not None

        inputs = self.tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            padding=True,
            max_length=256,
        )

        with torch.no_grad():
            outputs = self.model(**inputs)
            logits = outputs.logits
            probs = torch.softmax(logits, dim=-1).cpu().numpy()[0].tolist()

        # Generic handling for binary or multi-class heads
        if len(probs) == 2:
            # Assume index 1 = risky / misinfo-like
            risk_score = float(probs[1])
        else:
            # Conservative: use max non-zero-class probability as risk
            risk_score = float(max(probs[1:])) if len(probs) > 1 else float(probs[0])

        risk_score = _clip01(risk_score)

        if risk_score >= 0.75:
            label = "MISINFORMATION"
            stance = "spreading"
            confidence = risk_score
            explanation = "Transformer classifier found strong misinformation-like patterns."
        elif risk_score >= 0.45:
            label = "WARNING"
            stance = "warning"
            confidence = max(risk_score, 0.55)
            explanation = "Transformer classifier found suspicious or misleading patterns."
        else:
            label = "LOW_RISK"
            stance = "neutral"
            confidence = max(1.0 - risk_score, 0.55)
            explanation = "Transformer classifier found low-risk or ordinary content."

        return {
            "label": label,
            "stance": _normalise_stance(stance),
            "confidence": _clip01(confidence),
            "risk_score": risk_score,
            "probability": risk_score,
            "explanation": explanation,
            "model_name": self.local_model_dir or self.model_name,
            "mode": "transformer",
        }

    def _predict_fallback(self, text: str) -> Dict[str, Any]:
        """
        Rule-based fallback path.
        """
        lower = text.lower()

        debunk_keywords = [
            "fact check",
            "fact-check",
            "debunk",
            "debunked",
            "false claim",
            "misleading",
            "no evidence",
            "this is false",
            "not true",
            "hoax",
            "rumour",
            "rumor",
            "according to reuters",
            "according to ap",
            "according to bbc",
        ]

        strong_misinfo_keywords = [
            "secret cure",
            "cover-up",
            "what they don't want you to know",
            "mainstream media won't tell you",
            "microchip",
            "5g caused",
            "stolen election proof",
            "deep state",
            "bioweapon",
            "fake virus",
            "do your own research",
            "share before they delete this",
        ]

        suspicious_keywords = [
            "urgent",
            "breaking",
            "shocking",
            "exposed",
            "wake up",
            "share this",
            "they are hiding",
            "they lied",
            "massive fraud",
            "suppressed",
            "banned truth",
            "poison",
            "scamdemic",
            "plandemic",
        ]

        caution_keywords = [
            "alleged",
            "unverified",
            "reportedly",
            "claims that",
            "could be",
            "may be",
        ]

        positive_credible_keywords = [
            "official statement",
            "according to the cdc",
            "according to who",
            "according to nhs",
            "according to reuters",
            "according to the associated press",
            "court records show",
            "published study",
            "peer reviewed",
        ]

        debunk_hits = sum(1 for k in debunk_keywords if k in lower)
        strong_hits = sum(1 for k in strong_misinfo_keywords if k in lower)
        suspicious_hits = sum(1 for k in suspicious_keywords if k in lower)
        caution_hits = sum(1 for k in caution_keywords if k in lower)
        positive_hits = sum(1 for k in positive_credible_keywords if k in lower)

        # Extra pattern scoring
        all_caps_words = re.findall(r"\b[A-Z]{4,}\b", text)
        exclamations = text.count("!")
        urls = len(re.findall(r"https?://|www\.", lower))
        questions = text.count("?")

        risk_score = 0.08

        risk_score += strong_hits * 0.20
        risk_score += suspicious_hits * 0.10
        risk_score += caution_hits * 0.03
        risk_score += min(len(all_caps_words), 5) * 0.02
        risk_score += min(exclamations, 5) * 0.015
        risk_score += min(questions, 4) * 0.01

        # URLs alone are not bad, but lots of links in chain-message style can be noisy
        if urls >= 3:
            risk_score += 0.04

        # Debunking and authoritative language should reduce risk
        risk_score -= debunk_hits * 0.18
        risk_score -= positive_hits * 0.08

        risk_score = _clip01(risk_score)

        # Determine stance and label
        if debunk_hits >= 1 and strong_hits >= 1:
            stance = "debunking"
            label = "DEBUNKING"
            confidence = 0.78
            risk_score = min(risk_score, 0.20)
            explanation = "The text appears to discuss or debunk a misleading claim."
        elif risk_score >= 0.68:
            stance = "spreading"
            label = "MISINFORMATION"
            confidence = max(0.72, risk_score)
            explanation = "The text contains strong misinformation-like or conspiratorial patterns."
        elif risk_score >= 0.35:
            stance = "warning"
            label = "WARNING"
            confidence = max(0.58, risk_score)
            explanation = "The text contains suspicious or unverifiable patterns and should be checked."
        else:
            stance = "neutral"
            label = "LOW_RISK"
            confidence = max(0.60, 1.0 - risk_score)
            explanation = "The text appears ordinary, corrective, or low risk."

        return {
            "label": label,
            "stance": _normalise_stance(stance),
            "confidence": _clip01(confidence),
            "risk_score": _clip01(risk_score),
            "probability": _clip01(risk_score),
            "explanation": explanation,
            "model_name": "fallback-rules",
            "mode": "fallback",
            "signals": {
                "debunk_hits": debunk_hits,
                "strong_hits": strong_hits,
                "suspicious_hits": suspicious_hits,
                "caution_hits": caution_hits,
                "positive_hits": positive_hits,
            },
        }
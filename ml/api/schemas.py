from __future__ import annotations

from typing import Any, Dict, List, Optional, Literal
from pydantic import BaseModel, Field


class ApiBaseModel(BaseModel):
    model_config = {"protected_namespaces": ()}


class PredictRequest(ApiBaseModel):
    text: str = Field(..., description="Input text to analyse")
    enable_internet: bool = Field(
        default=True,
        description="Enable live internet verification against trusted sources",
    )


class EarlyBlock(ApiBaseModel):
    model_used: str
    prob_pos: float
    risk_band: str
    virality_score: Optional[float] = None


class ExplanationBlock(ApiBaseModel):
    user_summary: str = "Analysis complete."
    user_reasons: List[str] = []
    user_guidance: str = "Verify before sharing."
    final_explanation: str = "Analysis completed successfully."
    signals: Dict[str, Any] = {}
    key_phrases: List[Dict[str, Any]] = []


class AnalystTrigger(ApiBaseModel):
    name: str
    score: float
    explanation: str
    category: Optional[str] = "psychological"


class AnalystBlock(ApiBaseModel):
    triggers: List[AnalystTrigger] = []
    propagation_dynamics: Dict[str, Any] = {}
    human_susceptibility_logic: str = ""
    algorithmic_advantage: str = ""
    note: str = ""


class ModelBreakdown(ApiBaseModel):
    unified: float
    enhanced: Optional[float] = None
    legacy: Optional[float] = None
    ensemble: float


class MisinformationScore(ApiBaseModel):
    band: Literal["LOW", "MEDIUM", "HIGH"]
    probability: float
    raw_probability: Optional[float] = None
    explanation: str
    stance: Literal["debunking", "warning", "neutral", "spreading"]


class TacticsScore(ApiBaseModel):
    band: Literal["LOW", "MEDIUM", "HIGH"]
    intensity: float
    detected_triggers: List[Dict[str, Any]] = []
    overall_assessment: str = ""


class InternetSource(ApiBaseModel):
    title: str = ""
    url: str = ""
    snippet: str = ""
    domain: str = ""
    source_type: str = "general"
    credibility: float = 0.0
    evidence_direction: str = "mentions"


class InternetClaimResult(ApiBaseModel):
    claim: str
    verdict: Literal[
        "LIKELY_TRUE",
        "LEANING_TRUE",
        "LIKELY_FALSE",
        "LEANING_FALSE",
        "MIXED",
        "UNVERIFIED",
    ]
    confidence: float
    support_score: float = 0.0
    refute_score: float = 0.0
    mixed_score: float = 0.0
    sources: List[InternetSource] = []


class InternetVerification(ApiBaseModel):
    enabled: bool = True
    performed: bool = False
    overall_verdict: Literal["LIKELY_TRUE", "LIKELY_FALSE", "MIXED", "UNVERIFIED"] = "UNVERIFIED"
    overall_confidence: float = 0.0
    claims: List[InternetClaimResult] = []
    sources: List[InternetSource] = []
    summary_note: str = ""
    error: Optional[str] = None


class AutoPredictResponse(ApiBaseModel):
    request_id: str

    misinformation: MisinformationScore
    manipulation_tactics: TacticsScore

    action_verdict: Literal["SAFE_TO_SHARE", "VERIFY_REQUIRED", "LIKELY_MISINFORMATION"]
    action_reason: str
    override_note: Optional[str] = None

    confidence: float
    risk_band: Literal["LOW", "MEDIUM", "HIGH"]
    misinfo_probability: float

    model_breakdown: ModelBreakdown

    triggers: List[AnalystTrigger] = []

    early: Optional[EarlyBlock] = None
    explanation: ExplanationBlock
    analyst: Optional[AnalystBlock] = None

    internet_verification: Optional[InternetVerification] = None

    input_type: str = "text"
    extracted_text: Optional[str] = None
    filename: Optional[str] = None
    latency_ms: Optional[float] = None
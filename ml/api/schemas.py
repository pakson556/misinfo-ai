from __future__ import annotations

from typing import Any, Dict, List, Optional, Literal
from pydantic import BaseModel, Field


class ApiBaseModel(BaseModel):
    model_config = {"protected_namespaces": ()}


class PredictRequest(ApiBaseModel):
    text: str = Field(..., description="Input text to analyse")


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
    """Score for actual truthfulness/misinformation likelihood"""
    band: Literal["LOW", "MEDIUM", "HIGH"]
    probability: float  # 0-1 scale, final adjusted probability
    raw_probability: Optional[float] = None  # Raw model probability before adjustment
    explanation: str
    stance: Literal["debunking", "warning", "neutral", "spreading"]


class TacticsScore(ApiBaseModel):
    """Score for psychological manipulation tactics"""
    band: Literal["LOW", "MEDIUM", "HIGH"]
    intensity: float  # 0-1 scale
    detected_triggers: List[Dict[str, Any]] = []
    overall_assessment: str = ""


class AutoPredictResponse(ApiBaseModel):
    request_id: str
    
    # Split into two scores
    misinformation: MisinformationScore
    manipulation_tactics: TacticsScore
    
    # Keep original fields for backward compatibility
    action_verdict: Literal["SAFE_TO_SHARE", "VERIFY_REQUIRED", "LIKELY_MISINFORMATION"]
    action_reason: str
    override_note: Optional[str] = None
    
    # Confidence metrics
    confidence: float  # Overall confidence (max of two scores)
    risk_band: Literal["LOW", "MEDIUM", "HIGH"]  # For backward compatibility
    misinfo_probability: float  # Original p (ensemble)
    
    # Model breakdown
    model_breakdown: ModelBreakdown
    
    # Triggers
    triggers: List[AnalystTrigger] = []
    
    # Optional blocks
    early: Optional[EarlyBlock] = None
    explanation: ExplanationBlock
    analyst: Optional[AnalystBlock] = None
    
    # Input metadata
    input_type: str = "text"
    extracted_text: Optional[str] = None
    filename: Optional[str] = None
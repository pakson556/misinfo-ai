"""Public API contract. The frontend relies on these shapes."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl

ClaimVerdict = Literal["SUPPORTED", "REFUTED", "MIXED", "UNVERIFIABLE"]
Overall = Literal["LOOKS_RELIABLE", "NEEDS_CONTEXT", "LIKELY_FALSE", "UNVERIFIED", "NO_CLAIMS"]
EvidenceStance = Literal["supports", "refutes", "mixed", "neutral"]
SourceKind = Literal["factcheck", "news", "encyclopedia", "web", "government", "science"]


class AnalyzeTextRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Text to analyse")
    use_web: bool = Field(True, description="Search for evidence online")


class AnalyzeUrlRequest(BaseModel):
    url: HttpUrl
    use_web: bool = True


class Span(BaseModel):
    start: int
    end: int
    text: str


class Evidence(BaseModel):
    title: str = ""
    url: str = ""
    domain: str = ""
    snippet: str = ""
    kind: SourceKind = "web"
    publisher: str = ""
    rating: str | None = None  # textual rating from a fact-checker, e.g. "False"
    credibility: float = 0.5  # 0..1 prior for the domain
    stance: EvidenceStance = "neutral"
    published: str | None = None


class Claim(BaseModel):
    id: int
    text: str
    checkworthiness: float = 0.5
    span: Span | None = None


class ClaimResult(BaseModel):
    claim: Claim
    verdict: ClaimVerdict = "UNVERIFIABLE"
    confidence: float = 0.0
    reasoning: str = ""
    evidence: list[Evidence] = []
    method: Literal["llm", "factcheck_match", "heuristic"] = "heuristic"


class Tactic(BaseModel):
    id: str
    name: str
    description: str
    severity: float  # 0..1
    spans: list[Span] = []


class StyleSignal(BaseModel):
    available: bool = False
    model: str = ""
    probability: float | None = None  # P(text resembles misinformation in training data)
    note: str = ""


class PipelineInfo(BaseModel):
    llm_provider: str
    llm_model: str | None = None
    sources_used: list[str] = []
    timings_ms: dict[str, float] = {}
    warnings: list[str] = []


class AnalysisResult(BaseModel):
    id: str
    created_at: datetime
    input_type: Literal["text", "url", "image"] = "text"
    input_preview: str = ""
    input_text: str = ""  # full analysed text; spans index into this
    source_url: str | None = None
    extracted_text: str | None = None

    overall: Overall
    headline: str
    summary: str
    guidance: str
    risk: float  # 0..1, how likely the content is misleading
    confidence: float  # 0..1, how much evidence backs the judgement

    claims: list[ClaimResult] = []
    tactics: list[Tactic] = []
    tactics_score: float = 0.0
    style: StyleSignal = StyleSignal()
    pipeline: PipelineInfo


class HistoryItem(BaseModel):
    id: str
    created_at: datetime
    input_type: str
    input_preview: str
    overall: Overall
    risk: float
    confidence: float
    n_claims: int


class StatsResponse(BaseModel):
    total: int
    by_overall: dict[str, int]
    by_claim_verdict: dict[str, int]
    top_tactics: list[dict]
    avg_latency_ms: float | None
    daily: list[dict]


class HealthResponse(BaseModel):
    status: str
    version: str
    llm_provider: str
    llm_ready: bool
    style_model: str | None
    ocr: bool
    sources: dict[str, bool]

"""
The shapes of the data the backend sends and receives (the "API contract").

Each class is a Pydantic model: a description of a JSON object with typed fields.
FastAPI uses them to (1) check incoming data, (2) shape outgoing JSON, and
(3) generate the docs at /api/docs. The frontend relies on these exact field
names, so renaming a field here means updating frontend/src too.

The big one is AnalysisResult: the complete answer for one check. It nests
the others like this:

    AnalysisResult
    ├── claims:  [ClaimResult]        one per checked claim
    │             ├── claim: Claim    the claim text + where it sits in the input (Span)
    │             └── evidence: [Evidence]   sources found for it
    ├── tactics: [Tactic]             persuasion tricks spotted in the wording (with Spans)
    ├── style:   StyleSignal          optional trained-model score
    └── pipeline: PipelineInfo        which model/sources were used, timings, warnings
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

# "Literal" means only these exact strings are allowed.
ClaimVerdict = Literal["SUPPORTED", "REFUTED", "MIXED", "UNVERIFIABLE"]  # shown as True / False / Needs context / Unverified
Overall = Literal["LOOKS_RELIABLE", "NEEDS_CONTEXT", "LIKELY_FALSE", "UNVERIFIED", "NO_CLAIMS"]  # verdict for the whole text
EvidenceStance = Literal["supports", "refutes", "mixed", "neutral"]  # what one source says about one claim
SourceKind = Literal["factcheck", "news", "encyclopedia", "web", "government", "science"]


class Span(BaseModel):
    """A piece of the input text, by character position. Used to highlight claims and tactics in the UI."""

    start: int  # index of the first character
    end: int  # index just after the last character (Python slice style: text[start:end])
    text: str


class Evidence(BaseModel):
    """One source found while checking a claim (a fact-check article, Wikipedia page, news story, ...)."""

    title: str = ""
    url: str = ""
    domain: str = ""
    snippet: str = ""  # the relevant passage, used by the AI when judging
    kind: SourceKind = "web"
    publisher: str = ""
    rating: str | None = None  # fact-checker's own verdict text, e.g. "False" or "Half True"
    credibility: float = 0.5  # 0..1 starting trust for this website (see services/sources.py)
    stance: EvidenceStance = "neutral"  # filled in after the AI reads it
    published: str | None = None


class Claim(BaseModel):
    """One checkable factual statement pulled out of the input."""

    id: int
    text: str  # rewritten to make sense on its own ("he" -> the actual name, etc.)
    checkworthiness: float = 0.5  # 0..1: how important/checkable it is; weights the final verdict
    span: Span | None = None  # where it came from in the input (None if it couldn't be located)


class ClaimResult(BaseModel):
    """The verdict for one claim, with reasons and sources."""

    claim: Claim
    verdict: ClaimVerdict = "UNVERIFIABLE"
    confidence: float = 0.0  # 0..1, how strong the evidence is
    reasoning: str = ""  # plain-English explanation shown under the claim
    evidence: list[Evidence] = []
    method: Literal["llm", "factcheck_match", "heuristic"] = "heuristic"  # how the verdict was reached


class Tactic(BaseModel):
    """A persuasion technique found in the wording (e.g. "Pressure to share")."""

    id: str
    name: str
    description: str
    severity: float  # 0..1
    spans: list[Span] = []  # every place it appears, for the dotted underlines


class StyleSignal(BaseModel):
    """Result of the optional trained style model (see training/). Not used to decide verdicts."""

    available: bool = False
    model: str = ""
    probability: float | None = None  # how much the text resembles misinformation in the training data
    note: str = ""


class PipelineInfo(BaseModel):
    """Behind-the-scenes details, shown in small print at the bottom of a result."""

    llm_provider: str
    llm_model: str | None = None
    sources_used: list[str] = []  # e.g. ["google_factcheck", "wikipedia"]
    timings_ms: dict[str, float] = {}  # how long each stage took
    warnings: list[str] = []  # e.g. "wikipedia unavailable"; shown in amber in the UI


class AnalysisResult(BaseModel):
    """The complete answer for one check. Saved to the database and sent to the browser."""

    id: str  # short random id, used in shareable links: /a/<id>
    created_at: datetime
    input_type: Literal["text", "url", "image"] = "text"
    input_preview: str = ""  # first 280 characters, for the History list
    input_text: str = ""  # the full analysed text; all Span positions refer to this
    source_url: str | None = None  # set when the input was a link
    extracted_text: str | None = None  # set when the input was a screenshot (the OCR'd text)

    overall: Overall
    headline: str  # big title on the result page
    summary: str  # 2-3 sentence explanation
    guidance: str  # what the reader should do
    risk: float  # 0..1, how likely the content is misleading
    confidence: float  # 0..1, how much evidence backs the judgement

    claims: list[ClaimResult] = []
    tactics: list[Tactic] = []
    tactics_score: float = 0.0
    style: StyleSignal = StyleSignal()
    pipeline: PipelineInfo


class HistoryItem(BaseModel):
    """A short summary of a past check, for the History list."""

    id: str
    created_at: datetime
    input_type: str
    input_preview: str
    overall: Overall
    risk: float
    confidence: float
    n_claims: int


class StatsResponse(BaseModel):
    """Numbers for the Insights page."""

    total: int
    by_overall: dict[str, int]
    by_claim_verdict: dict[str, int]
    top_tactics: list[dict]
    avg_latency_ms: float | None
    daily: list[dict]


class HealthResponse(BaseModel):
    """Answer from /api/health: what's switched on."""

    status: str
    version: str
    llm_provider: str
    llm_ready: bool  # False -> the website shows the yellow "basic mode" banner
    style_model: str | None
    ocr: bool  # can it read screenshots (is Tesseract installed)?
    sources: dict[str, bool]  # which evidence sources are switched on

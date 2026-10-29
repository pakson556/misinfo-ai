"""Analysis history (SQLite by default, any SQLAlchemy URL works, e.g. Postgres)."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from functools import lru_cache

from sqlmodel import Field, Session, SQLModel, create_engine, select

from .config import get_settings
from .schemas import AnalysisResult, HistoryItem, StatsResponse


class AnalysisRow(SQLModel, table=True):
    __tablename__ = "analyses"

    id: str = Field(primary_key=True)
    created_at: datetime = Field(index=True)
    input_type: str
    input_preview: str = ""
    overall: str = Field(index=True)
    risk: float
    confidence: float
    n_claims: int
    latency_ms: float | None = None
    claim_verdicts: str = "[]"  # json list
    tactic_ids: str = "[]"  # json list
    result_json: str


@lru_cache
def engine():
    url = get_settings().db_url
    kw = {"connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {"pool_pre_ping": True}
    eng = create_engine(url, **kw)
    SQLModel.metadata.create_all(eng)
    return eng


def save(result: AnalysisResult) -> None:
    s = get_settings()
    r = result
    if not s.store_input_text:
        r = result.model_copy(update={"input_preview": "", "input_text": "", "extracted_text": None})
    row = AnalysisRow(
        id=r.id,
        created_at=r.created_at,
        input_type=r.input_type,
        input_preview=r.input_preview[:280],
        overall=r.overall,
        risk=r.risk,
        confidence=r.confidence,
        n_claims=len(r.claims),
        latency_ms=r.pipeline.timings_ms.get("total"),
        claim_verdicts=json.dumps([c.verdict for c in r.claims]),
        tactic_ids=json.dumps([t.id for t in r.tactics]),
        result_json=r.model_dump_json(),
    )
    with Session(engine()) as ses:
        ses.merge(row)
        ses.commit()


def get(analysis_id: str) -> AnalysisResult | None:
    with Session(engine()) as ses:
        row = ses.get(AnalysisRow, analysis_id)
        return AnalysisResult.model_validate_json(row.result_json) if row else None


def delete(analysis_id: str) -> bool:
    with Session(engine()) as ses:
        row = ses.get(AnalysisRow, analysis_id)
        if not row:
            return False
        ses.delete(row)
        ses.commit()
        return True


def history(limit: int = 50, offset: int = 0) -> list[HistoryItem]:
    with Session(engine()) as ses:
        rows = ses.exec(select(AnalysisRow).order_by(AnalysisRow.created_at.desc()).offset(offset).limit(limit)).all()
    return [
        HistoryItem(
            id=r.id,
            created_at=r.created_at,
            input_type=r.input_type,
            input_preview=r.input_preview,
            overall=r.overall,
            risk=r.risk,
            confidence=r.confidence,
            n_claims=r.n_claims,
        )
        for r in rows
    ]


TACTIC_NAMES = {
    "virality_call": "Pressure to share",
    "urgency": "Artificial urgency",
    "conspiracy": "Conspiracy framing",
    "false_authority": "Vague or false authority",
    "emotional": "Emotionally charged language",
    "absolutes": "Absolute certainty",
    "scapegoating": "Scapegoating",
    "false_dichotomy": "False dilemma",
    "miracle_health": "Miracle health claim",
    "shouting": "Shouting (ALL CAPS)",
    "excess_punctuation": "Excessive punctuation",
}


def stats(days: int = 30) -> StatsResponse:
    with Session(engine()) as ses:
        rows = ses.exec(select(AnalysisRow).order_by(AnalysisRow.created_at.desc()).limit(5000)).all()
    by_overall = Counter(r.overall for r in rows)
    verdicts: Counter = Counter()
    tactics: Counter = Counter()
    lat = [r.latency_ms for r in rows if r.latency_ms]
    daily: dict[str, dict] = defaultdict(lambda: {"count": 0, "risk_sum": 0.0, "false": 0})
    now = datetime.now(UTC)
    for r in rows:
        verdicts.update(json.loads(r.claim_verdicts))
        tactics.update(json.loads(r.tactic_ids))
        created = r.created_at if r.created_at.tzinfo else r.created_at.replace(tzinfo=UTC)
        if (now - created).days < days:
            d = daily[created.date().isoformat()]
            d["count"] += 1
            d["risk_sum"] += r.risk
            d["false"] += r.overall == "LIKELY_FALSE"
    return StatsResponse(
        total=len(rows),
        by_overall=dict(by_overall),
        by_claim_verdict=dict(verdicts),
        top_tactics=[{"id": k, "name": TACTIC_NAMES.get(k, k), "count": v} for k, v in tactics.most_common(8)],
        avg_latency_ms=round(sum(lat) / len(lat), 1) if lat else None,
        daily=[
            {"date": k, "count": v["count"], "avg_risk": round(v["risk_sum"] / v["count"], 3), "likely_false": v["false"]}
            for k, v in sorted(daily.items())
        ],
    )

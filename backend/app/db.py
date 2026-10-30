"""
Saved history of checks: the database layer.

WHERE THE DATA LIVES
    By default a single SQLite file: backend/data/misinfo.db (in Docker, it's
    inside the "misinfo-data" volume so it survives restarts). Set DATABASE_URL
    to use a real database server such as Postgres instead; no code changes needed.

HOW IT'S STORED
    One table, "analyses", with one row per check. Most columns are small
    summary values (overall verdict, risk, ...) so the History and Insights
    pages can list and count quickly. The complete result is also kept as JSON
    in `result_json`, so opening an old check shows exactly what was shown originally.

SQLModel is the library used: you describe a table as a Python class and it
writes the SQL for you.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from functools import lru_cache

from sqlmodel import Field, Session, SQLModel, create_engine, select

from .config import get_settings
from .pipeline.tactics import TACTIC_NAMES
from .schemas import AnalysisResult, HistoryItem, StatsResponse


class AnalysisRow(SQLModel, table=True):
    """One row of the `analyses` table = one saved check."""

    __tablename__ = "analyses"

    id: str = Field(primary_key=True)
    created_at: datetime = Field(index=True)  # index = fast sorting by date
    input_type: str
    input_preview: str = ""
    overall: str = Field(index=True)
    risk: float
    confidence: float
    n_claims: int
    latency_ms: float | None = None
    claim_verdicts: str = "[]"  # JSON list, e.g. '["REFUTED","SUPPORTED"]' (for Insights counts)
    tactic_ids: str = "[]"  # JSON list of tactic ids found (for Insights counts)
    result_json: str  # the full AnalysisResult as JSON


@lru_cache  # create the connection pool once and reuse it
def engine():
    """Connect to the database and create the table if it doesn't exist yet."""
    url = get_settings().db_url
    # SQLite needs check_same_thread=False because FastAPI serves requests from several threads.
    kw = {"connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {"pool_pre_ping": True}
    eng = create_engine(url, **kw)
    SQLModel.metadata.create_all(eng)
    return eng


def save(result: AnalysisResult) -> None:
    """Store a finished check. Called by main.py when the pipeline produces its final result."""
    s = get_settings()
    r = result
    if not s.store_input_text:
        # Privacy mode: keep the verdict but forget what the person pasted.
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
    with Session(engine()) as ses:  # a Session is one conversation with the database
        ses.merge(row)  # insert, or update if a row with this id already exists
        ses.commit()  # actually write it to disk


def get(analysis_id: str) -> AnalysisResult | None:
    """Load one full check by id, or None if it doesn't exist."""
    with Session(engine()) as ses:
        row = ses.get(AnalysisRow, analysis_id)
        return AnalysisResult.model_validate_json(row.result_json) if row else None


def delete(analysis_id: str) -> bool:
    """Delete one check. Returns False if there was nothing to delete."""
    with Session(engine()) as ses:
        row = ses.get(AnalysisRow, analysis_id)
        if not row:
            return False
        ses.delete(row)
        ses.commit()
        return True


def history(limit: int = 50, offset: int = 0) -> list[HistoryItem]:
    """Newest checks first, as short summaries. `offset` allows paging through older ones."""
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


def stats(days: int = 30) -> StatsResponse:
    """Counts and per-day totals for the Insights page (looks at up to the last 5,000 checks)."""
    with Session(engine()) as ses:
        rows = ses.exec(select(AnalysisRow).order_by(AnalysisRow.created_at.desc()).limit(5000)).all()

    by_overall = Counter(r.overall for r in rows)  # e.g. {"LIKELY_FALSE": 3, "LOOKS_RELIABLE": 1}
    verdicts: Counter = Counter()
    tactics: Counter = Counter()
    lat = [r.latency_ms for r in rows if r.latency_ms]
    # One bucket per calendar day for the bar chart.
    daily: dict[str, dict] = defaultdict(lambda: {"count": 0, "risk_sum": 0.0, "false": 0})
    now = datetime.now(UTC)

    for r in rows:
        verdicts.update(json.loads(r.claim_verdicts))
        tactics.update(json.loads(r.tactic_ids))
        # SQLite drops timezone info, so treat stored times as UTC.
        created = r.created_at if r.created_at.tzinfo else r.created_at.replace(tzinfo=UTC)
        if (now - created).days < days:
            d = daily[created.date().isoformat()]
            d["count"] += 1
            d["risk_sum"] += r.risk
            d["false"] += r.overall == "LIKELY_FALSE"  # True counts as 1

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

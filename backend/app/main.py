"""FastAPI application."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl, model_validator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sse_starlette.sse import EventSourceResponse

from . import db
from .config import get_settings
from .llm import get_provider
from .llm.heuristic_provider import HeuristicProvider
from .pipeline.ingest import IngestError, fetch_article, ocr_available, ocr_image
from .pipeline.orchestrator import run_analysis
from .pipeline.retrieval import active_sources
from .pipeline.style import style_model_name
from .schemas import AnalysisResult, HealthResponse, HistoryItem, StatsResponse
from .services import http

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("misinfo")
settings = get_settings()
limiter = Limiter(key_func=get_remote_address, default_limits=[])


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.engine()
    p = get_provider()
    log.info(
        "MisInfo AI %s | llm=%s model=%s | style=%s | sources=%s",
        settings.version,
        p.name,
        p.model,
        style_model_name(),
        active_sources(),
    )
    yield
    await http.aclose()


app = FastAPI(
    title=settings.app_name, version=settings.version, lifespan=lifespan, docs_url="/api/docs", openapi_url="/api/openapi.json"
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(CORSMiddleware, allow_origins=settings.origins, allow_methods=["GET", "POST", "DELETE"], allow_headers=["*"])


class AnalyzeRequest(BaseModel):
    text: str | None = None
    url: HttpUrl | None = None
    use_web: bool = True

    @model_validator(mode="after")
    def one_input(self):
        if bool(self.text and self.text.strip()) == bool(self.url):
            raise ValueError("Provide exactly one of 'text' or 'url'.")
        if self.text and len(self.text) > settings.max_input_chars:
            raise ValueError(f"Text is too long (max {settings.max_input_chars} characters).")
        return self


async def _prepare(req: AnalyzeRequest) -> dict:
    if req.url:
        art = await fetch_article(str(req.url))
        body = f"{art.title}\n\n{art.text}" if art.title else art.text
        return {"text": body, "input_type": "url", "source_url": art.url, "use_web": req.use_web}
    return {"text": req.text or "", "input_type": "text", "use_web": req.use_web}


async def _stream(kwargs: dict) -> AsyncIterator[dict]:
    """Run the pipeline, persist the result, and format events for SSE."""
    try:
        async for e in run_analysis(**kwargs):
            if e["event"] == "result":
                try:
                    await asyncio.to_thread(db.save, AnalysisResult.model_validate(e["data"]))
                except Exception:  # noqa: BLE001 - history must never break analysis
                    log.exception("failed to save analysis")
            yield {"event": e["event"], "data": json.dumps(e["data"])}
    except asyncio.CancelledError:
        raise
    except Exception as ex:  # noqa: BLE001
        log.exception("pipeline error")
        yield {"event": "error", "data": json.dumps({"message": f"Analysis failed: {type(ex).__name__}"})}


# ----------------------------------------------------------------- routes


@app.get("/api/health", response_model=HealthResponse)
def health():
    p = get_provider()
    return HealthResponse(
        status="ok",
        version=settings.version,
        llm_provider=p.name,
        llm_ready=not isinstance(p, HeuristicProvider),
        style_model=style_model_name(),
        ocr=ocr_available(),
        sources=active_sources(),
    )


@app.post("/api/analyze", response_model=AnalysisResult)
@limiter.limit(settings.rate_limit)
async def analyze(request: Request, req: AnalyzeRequest):
    try:
        kwargs = await _prepare(req)
    except IngestError as e:
        raise HTTPException(422, str(e)) from e
    async for e in _stream(kwargs):
        if e["event"] == "result":
            return json.loads(e["data"])
        if e["event"] == "error":
            raise HTTPException(500, json.loads(e["data"])["message"])
    raise HTTPException(500, "No result produced")


@app.post("/api/analyze/stream")
@limiter.limit(settings.rate_limit)
async def analyze_stream(request: Request, req: AnalyzeRequest):
    try:
        kwargs = await _prepare(req)
    except IngestError as e:
        raise HTTPException(422, str(e)) from e
    return EventSourceResponse(_stream(kwargs), ping=10)


@app.post("/api/analyze/image/stream")
@limiter.limit(settings.rate_limit)
async def analyze_image_stream(request: Request, file: UploadFile = File(...), use_web: bool = Query(True)):
    raw = await file.read(settings.max_upload_mb * 1024 * 1024 + 1)
    if len(raw) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"Image is larger than {settings.max_upload_mb} MB.")
    try:
        text = await ocr_image(raw)
    except IngestError as e:
        raise HTTPException(422, str(e)) from e
    return EventSourceResponse(
        _stream({"text": text, "input_type": "image", "extracted_text": text, "use_web": use_web}), ping=10
    )


@app.get("/api/history", response_model=list[HistoryItem])
def list_history(limit: int = Query(50, le=200), offset: int = Query(0, ge=0)):
    return db.history(limit, offset)


@app.get("/api/history/{analysis_id}", response_model=AnalysisResult)
def get_analysis(analysis_id: str):
    r = db.get(analysis_id)
    if not r:
        raise HTTPException(404, "Not found")
    return r


@app.delete("/api/history/{analysis_id}")
def delete_analysis(analysis_id: str):
    if not db.delete(analysis_id):
        raise HTTPException(404, "Not found")
    return {"deleted": analysis_id}


@app.get("/api/stats", response_model=StatsResponse)
def stats(days: int = Query(30, ge=1, le=365)):
    return db.stats(days)

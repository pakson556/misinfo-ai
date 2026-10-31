"""
The web server: the "front door" of the backend.

WHAT THIS FILE DOES
    It creates the FastAPI app and defines every URL (an "endpoint" or "route")
    the website can call, for example POST /api/analyze/stream. Each route
    checks the request, hands the real work to the pipeline (pipeline/), and
    sends the answer back.

HOW A CHECK FLOWS THROUGH HERE
    browser --POST /api/analyze/stream--> analyze_stream()
        -> _prepare()   turns a link into article text (text input passes through)
        -> _stream()    runs pipeline/orchestrator.run_analysis() and forwards each
                        progress event to the browser as it happens, then saves
                        the final result to the database (db.py)

HOW TO RUN IT ON ITS OWN
    cd backend && uvicorn app.main:app --reload
    then open http://localhost:8000/api/docs for clickable, auto-generated API docs.
    (In Docker this same command runs inside the "backend" container.)
"""

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
from . import monitor as monitor_mod
from .config import get_settings
from .llm import get_provider
from .llm.heuristic_provider import HeuristicProvider
from .pipeline.ingest import IngestError, fetch_article, ocr_available, ocr_image
from .pipeline.orchestrator import run_analysis
from .pipeline.retrieval import active_sources
from .pipeline.style import style_model_name
from .schemas import AnalysisResult, HealthResponse, HistoryItem, StatsResponse
from .services import http

# Log lines look like: "2026-10-30 17:20:01 INFO misinfo: ..."; you see them in
# the terminal (or in Docker Desktop > Containers > backend > Logs).
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("misinfo")

# All settings (API keys, limits, ...) come from environment variables / backend/.env.
settings = get_settings()

# Rate limiting: stops one visitor from running hundreds of (paid) checks a minute.
# Each visitor is identified by their IP address. The limit is set by RATE_LIMIT in .env.
limiter = Limiter(key_func=get_remote_address, default_limits=[])


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Code that runs once when the server starts (before `yield`) and once when it stops (after)."""
    db.engine()  # create the database file and tables if they don't exist yet
    p = get_provider()
    # One summary line at start-up so you can see straight away what is switched on.
    log.info(
        "MisInfo AI %s | llm=%s model=%s | style=%s | sources=%s",
        settings.version,
        p.name,
        p.model,
        style_model_name(),
        active_sources(),
    )
    # Live monitor: a background task that reads the public Bluesky stream (see monitor.py).
    task = asyncio.create_task(monitor_mod.run_forever()) if settings.monitor_enabled else None
    yield
    if task:
        task.cancel()
    await http.aclose()  # close the shared HTTP client cleanly on shutdown


app = FastAPI(
    title=settings.app_name, version=settings.version, lifespan=lifespan, docs_url="/api/docs", openapi_url="/api/openapi.json"
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS = which websites may call this API from a browser. Without this, a browser
# blocks the frontend (e.g. http://localhost:5173) from talking to the backend
# (http://localhost:8000) because they're on different ports. Set by CORS_ORIGINS.
app.add_middleware(CORSMiddleware, allow_origins=settings.origins, allow_methods=["GET", "POST", "DELETE"], allow_headers=["*"])


class AnalyzeRequest(BaseModel):
    """
    The JSON body the website sends to start a check.

    Pydantic validates it automatically: if the browser sends something wrong,
    FastAPI replies with a 422 error explaining what's wrong and our code never runs.
    """

    text: str | None = None  # pasted text...
    url: HttpUrl | None = None  # ...or a link to an article (never both)
    use_web: bool = True  # the "Search the web for evidence" checkbox

    @model_validator(mode="after")
    def one_input(self):
        # Exactly one of text / url must be given.
        if bool(self.text and self.text.strip()) == bool(self.url):
            raise ValueError("Provide exactly one of 'text' or 'url'.")
        if self.text and len(self.text) > settings.max_input_chars:
            raise ValueError(f"Text is too long (max {settings.max_input_chars} characters).")
        return self


async def _prepare(req: AnalyzeRequest) -> dict:
    """Turn the request into the arguments run_analysis() needs. For a URL, download the article first."""
    if req.url:
        art = await fetch_article(str(req.url))  # may raise IngestError (e.g. page not found)
        body = f"{art.title}\n\n{art.text}" if art.title else art.text
        return {"text": body, "input_type": "url", "source_url": art.url, "use_web": req.use_web}
    return {"text": req.text or "", "input_type": "text", "use_web": req.use_web}


async def _stream(kwargs: dict) -> AsyncIterator[dict]:
    """
    Run the pipeline, save the final result, and format each event for streaming.

    The pipeline yields events like {"event": "claims", "data": {...}} as it works.
    We pass each one straight to the browser so the page updates live.
    """
    try:
        async for e in run_analysis(**kwargs):
            if e["event"] == "result":
                # Final answer: save it to history. Done in a thread because the
                # database library is synchronous and would otherwise pause the server.
                try:
                    await asyncio.to_thread(db.save, AnalysisResult.model_validate(e["data"]))
                except Exception:  # noqa: BLE001 - history must never break analysis
                    log.exception("failed to save analysis")
            yield {"event": e["event"], "data": json.dumps(e["data"])}
    except asyncio.CancelledError:
        raise  # the user closed the tab / pressed Stop: let it end quietly
    except Exception as ex:  # noqa: BLE001
        log.exception("pipeline error")
        yield {"event": "error", "data": json.dumps({"message": f"Analysis failed: {type(ex).__name__}"})}


# ----------------------------------------------------------------- routes
# Each function below handles one URL. The decorator (@app.get / @app.post)
# says which URL and HTTP method it answers.


@app.get("/api/health", response_model=HealthResponse)
def health():
    """Quick status check. The website calls this on load to show the "basic mode" banner if no AI is set up."""
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
    """
    Non-streaming version: waits for the whole check, then returns the final result as JSON.
    Handy for scripts and testing (the website uses the streaming version below).
    """
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
    """
    The main endpoint the website uses for text and links.

    Returns Server-Sent Events (SSE): a response that stays open and delivers
    events one by one ("claims found", "claim 1 checked", ...). That is how
    claims turn red/green on screen while the check is still running.
    """
    try:
        kwargs = await _prepare(req)
    except IngestError as e:
        raise HTTPException(422, str(e)) from e
    return EventSourceResponse(_stream(kwargs), ping=10)  # ping keeps the connection alive


@app.post("/api/analyze/image/stream")
@limiter.limit(settings.rate_limit)
async def analyze_image_stream(request: Request, file: UploadFile = File(...), use_web: bool = Query(True)):
    """Same as above, but for an uploaded screenshot: read the text out of the image (OCR) first."""
    # Read at most max_upload_mb + 1 byte, so a huge upload can't fill the server's memory.
    raw = await file.read(settings.max_upload_mb * 1024 * 1024 + 1)
    if len(raw) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"That picture is too big. Please use one smaller than {settings.max_upload_mb} MB.")
    try:
        text = await ocr_image(raw)
    except IngestError as e:
        raise HTTPException(422, str(e)) from e
    return EventSourceResponse(
        _stream({"text": text, "input_type": "image", "extracted_text": text, "use_web": use_web}), ping=10
    )


# --- History and Insights pages -----------------------------------------------


@app.get("/api/history", response_model=list[HistoryItem])
def list_history(limit: int = Query(50, le=200), offset: int = Query(0, ge=0)):
    """List past checks, newest first (History page)."""
    return db.history(limit, offset)


@app.get("/api/history/{analysis_id}", response_model=AnalysisResult)
def get_analysis(analysis_id: str):
    """One saved check in full (opened from History, or via a shared /a/<id> link)."""
    r = db.get(analysis_id)
    if not r:
        raise HTTPException(404, "Not found")
    return r


@app.delete("/api/history/{analysis_id}")
def delete_analysis(analysis_id: str):
    """Delete one saved check (bin icon on the History page)."""
    if not db.delete(analysis_id):
        raise HTTPException(404, "Not found")
    return {"deleted": analysis_id}


@app.get("/api/monitor")
def live_monitor():
    """Counters and recently flagged posts for the Live page (empty while the monitor is off)."""
    return monitor_mod.monitor.snapshot()


@app.get("/api/stats", response_model=StatsResponse)
def stats(days: int = Query(30, ge=1, le=365)):
    """Totals and charts for the Insights page."""
    return db.stats(days)

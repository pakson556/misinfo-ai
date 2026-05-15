#!/usr/bin/env python3
"""
Main FastAPI application for misinformation detection.

Updated version:
- Optional internet verification on /predict/auto
- Existing ML pipeline preserved
- OCR image route preserved
- Dashboard metrics endpoints preserved
"""

import time
import traceback
import uuid
from pathlib import Path
from typing import Any, Optional

import joblib
from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .config import (
    ALLOWED_ORIGINS,
    APP_VERSION,
    DEFAULT_THRESHOLD_HEALTH,
    DEFAULT_THRESHOLD_UNIFIED,
    ENHANCED_EARLY_MODEL,
    EVENTS_LOG,
    LEGACY_EARLY_MODEL,
    MODEL_HEALTH,
    MODEL_UNIFIED,
    THRESHOLD_HEALTH,
    THRESHOLD_UNIFIED,
)
from .models import load_model_with_threshold, log_event
from .metrics_service import build_global_monitor, build_metrics
from .ocr_service import (
    OCR_AVAILABLE,
    configure_tesseract,
    extract_text_from_image_bytes,
)
from .predict_service import run_predict_auto
from .schemas import AutoPredictResponse, PredictRequest
from .live_feed_service import get_live_feed

app = FastAPI(title="MisInfo AI", version=APP_VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

unified_model: Optional[Any] = None
health_model: Optional[Any] = None
legacy_early_model: Optional[Any] = None
enhanced_early_model: Optional[Any] = None
bert_classifier: Optional[Any] = None

BASE_DIR = Path(__file__).resolve().parent.parent
MODELS_DIR = BASE_DIR / "data" / "models"


@app.on_event("startup")
def startup() -> None:
    global unified_model, health_model, legacy_early_model, enhanced_early_model, bert_classifier

    print("=" * 60)
    print("Starting ML API")
    print("=" * 60)

    try:
        unified_model, unified_threshold = load_model_with_threshold(
            MODEL_UNIFIED,
            THRESHOLD_UNIFIED,
            DEFAULT_THRESHOLD_UNIFIED,
        )
        print(f"Loaded unified model (threshold={unified_threshold})")
    except Exception as e:
        print(f"Failed to load unified model: {e}")
        traceback.print_exc()
        unified_model = None

    try:
        if MODEL_HEALTH.exists():
            health_model, health_threshold = load_model_with_threshold(
                MODEL_HEALTH,
                THRESHOLD_HEALTH,
                DEFAULT_THRESHOLD_HEALTH,
            )
            print(f"Loaded health model (threshold={health_threshold})")
        else:
            print("Health model not found (optional).")
            health_model = None
    except Exception as e:
        print(f"Failed to load health model: {e}")
        traceback.print_exc()
        health_model = None

    try:
        if ENHANCED_EARLY_MODEL.exists():
            enhanced_early_model = joblib.load(ENHANCED_EARLY_MODEL)
            print("Loaded enhanced early model")
        else:
            print("Enhanced early model not found (optional).")
            enhanced_early_model = None
    except Exception as e:
        print(f"Failed to load enhanced early model: {e}")
        traceback.print_exc()
        enhanced_early_model = None

    try:
        if LEGACY_EARLY_MODEL.exists():
            legacy_early_model = joblib.load(LEGACY_EARLY_MODEL)
            print("Loaded legacy early model")
        else:
            print("Legacy early model not found (optional).")
            legacy_early_model = None
    except Exception as e:
        print(f"Failed to load legacy early model: {e}")
        traceback.print_exc()
        legacy_early_model = None

    try:
        from .bert_classifier import BertMisinformationClassifier

        bert_classifier = BertMisinformationClassifier()
        print("Loaded bert_classifier")
    except Exception as e:
        print(f"bert_classifier not loaded (optional): {e}")
        traceback.print_exc()
        bert_classifier = None

    if OCR_AVAILABLE:
        try:
            configure_tesseract()
        except Exception as e:
            print(f"OCR configuration warning: {e}")

    print("=" * 60)
    print(f"API ready. Version: {APP_VERSION}")
    print("=" * 60)


def _safe_float(x):
    try:
        return float(x)
    except Exception:
        return None


def _event_ts_seconds(event: dict) -> Optional[int]:
    from datetime import datetime, timezone

    raw = event.get("ts") or event.get("timestamp") or event.get("created_at")
    if raw is None:
        return None

    if isinstance(raw, (int, float)):
        n = float(raw)
        return int(n / 1000) if n >= 10_000_000_000 else int(n)

    if isinstance(raw, str):
        s = raw.strip()
        if not s:
            return None

        try:
            n = float(s)
            return int(n / 1000) if n >= 10_000_000_000 else int(n)
        except Exception:
            pass

        try:
            s2 = s.replace("Z", "+00:00")
            dt = datetime.fromisoformat(s2)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            dt_utc = dt.astimezone(timezone.utc)
            return int(dt_utc.timestamp())
        except Exception:
            return None

    return None


@app.get("/health")
def health():
    return {
        "status": "ok",
        "version": APP_VERSION,
        "models": {
            "unified": unified_model is not None,
            "health": health_model is not None,
            "enhanced_early": enhanced_early_model is not None,
            "legacy_early": legacy_early_model is not None,
            "bert_classifier": bert_classifier is not None,
        },
        "ocr_available": OCR_AVAILABLE,
        "events_log": str(EVENTS_LOG),
    }


@app.post("/predict/auto", response_model=AutoPredictResponse)
def predict_auto(req: PredictRequest, request: Request):
    if unified_model is None:
        raise HTTPException(status_code=500, detail="Unified model not loaded")

    rid = str(uuid.uuid4())
    start = time.time()

    try:
        resp = run_predict_auto(
            text=req.text,
            request_id=rid,
            endpoint=str(request.url.path),
            unified_model=unified_model,
            health_model=health_model,
            enhanced_early_model=enhanced_early_model,
            legacy_early_model=legacy_early_model,
            bert_classifier=bert_classifier,
            enable_internet=req.enable_internet,
        )

        resp["latency_ms"] = round((time.time() - start) * 1000, 2)

        try:
            log_event(
                request_id=rid,
                endpoint=str(request.url.path),
                event_type="predict",
                model_name="ensemble",
                input_payload={
                    "text": (req.text or "")[:5000],
                    "enable_internet": bool(req.enable_internet),
                },
                output_payload=resp,
                path=EVENTS_LOG,
            )
        except Exception as e:
            print(f"⚠️ Logging failed: {e}")
            traceback.print_exc()

        return resp

    except ValueError as ve:
        raise HTTPException(status_code=422, detail=str(ve))
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/predict/auto/image", response_model=AutoPredictResponse)
async def predict_auto_image(
    request: Request,
    file: UploadFile = File(...),
    enable_internet: bool = Query(True),
):
    if unified_model is None:
        raise HTTPException(status_code=500, detail="Unified model not loaded")

    if not OCR_AVAILABLE:
        raise HTTPException(
            status_code=500,
            detail="OCR not available. Install: pip install pytesseract pillow",
        )

    raw = await file.read()

    try:
        extracted = extract_text_from_image_bytes(raw)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"OCR failed: {e}")

    if not extracted:
        raise HTTPException(
            status_code=422,
            detail="OCR extracted no usable text. Try a clearer screenshot.",
        )

    req2 = PredictRequest(text=extracted, enable_internet=enable_internet)
    resp = predict_auto(req2, request)

    resp["input_type"] = "image_ocr"
    resp["extracted_text"] = extracted
    resp["filename"] = file.filename
    return resp


@app.get("/models/info")
def models_info():
    return {
        "unified": str(MODEL_UNIFIED),
        "health": str(MODEL_HEALTH),
        "enhanced_early": str(ENHANCED_EARLY_MODEL),
        "legacy_early": str(LEGACY_EARLY_MODEL),
        "bert_classifier": bool(bert_classifier),
        "events_log": str(EVENTS_LOG),
    }


@app.get("/trends")
def trends(limit: int = 20, window: int = 2000):
    return build_global_monitor(events_log=EVENTS_LOG, limit=limit, window=window)


@app.get("/dashboard/metrics")
def dashboard_metrics(window: int = 2000, recent: int = 10, bucket_seconds: int = 60):
    import json
    from collections import defaultdict

    generated_at = int(time.time())

    events = []
    if EVENTS_LOG.exists():
        try:
            with open(EVENTS_LOG, "r", encoding="utf-8") as f:
                lines = f.readlines()[-window:]
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except Exception:
                    continue
        except Exception:
            events = []

    if not events:
        return {
            "totals": {"analyses": 0},
            "bands": {},
            "verdicts": {},
            "stance": {},
            "latency_ms": {"avg": None, "p95": None},
            "risk": {"avg": None, "min": None, "max": None},
            "confidence": {"avg": None, "min": None, "max": None},
            "timeseries": [],
            "recent": [],
            "events_log": str(EVENTS_LOG),
            "generated_at": generated_at,
        }

    totals = {"analyses": len(events)}

    bands = defaultdict(int)
    verdicts = defaultdict(int)
    stance_dist = defaultdict(int)

    risks = []
    confidences = []
    latencies_ms = []

    buckets = defaultdict(lambda: {"count": 0, "risk_sum": 0.0})

    for event in events:
        output = event.get("output_payload") or event.get("output") or {}

        band = output.get("risk_band") or "UNKNOWN"
        bands[band] += 1

        verdict = output.get("action_verdict") or "UNKNOWN"
        verdicts[verdict] += 1

        misinfo = output.get("misinformation") or {}
        stance = misinfo.get("stance") or output.get("stance") or "unknown"
        stance_dist[stance] += 1

        risk = _safe_float(output.get("misinfo_probability"))
        if risk is not None:
            risks.append(risk)

        conf = _safe_float(output.get("confidence"))
        if conf is not None:
            confidences.append(conf)

        latency = output.get("latency_ms") or event.get("latency_ms")
        latency_f = _safe_float(latency)
        if latency_f is not None:
            latencies_ms.append(latency_f)

        tsec = _event_ts_seconds(event)
        if tsec is not None:
            b = int(tsec // bucket_seconds) * bucket_seconds
            buckets[int(b)]["count"] += 1
            if risk is not None:
                buckets[int(b)]["risk_sum"] += float(risk)

    avg_risk = (sum(risks) / len(risks)) if risks else None
    avg_conf = (sum(confidences) / len(confidences)) if confidences else None

    lat_avg = (sum(latencies_ms) / len(latencies_ms)) if latencies_ms else None
    lat_p95 = None
    if latencies_ms:
        xs = sorted(latencies_ms)
        idx = int(round(0.95 * (len(xs) - 1)))
        lat_p95 = xs[idx]

    timeseries = []
    for t_bucket in sorted(buckets.keys()):
        c = buckets[t_bucket]["count"]
        rs = buckets[t_bucket]["risk_sum"]
        avg = (rs / c) if c > 0 else 0.0
        timeseries.append({"t": int(t_bucket), "avg_risk": float(avg), "count": int(c)})

    recent_rows = []
    tail = events[-recent:] if recent > 0 else []
    for event in tail:
        output = event.get("output_payload") or event.get("output") or {}
        misinfo = output.get("misinformation") or {}

        inp = event.get("input_payload") or event.get("input") or {}
        text = (inp.get("text") or "").strip()
        if len(text) > 120:
            text = text[:117] + "..."

        recent_rows.append(
            {
                "request_id": output.get("request_id") or event.get("request_id") or "",
                "ts": _event_ts_seconds(event),
                "text_preview": text or "(no preview)",
                "risk_band": output.get("risk_band") or "",
                "verdict": output.get("action_verdict") or "",
                "misinfo_probability": _safe_float(output.get("misinfo_probability")),
                "confidence": _safe_float(output.get("confidence")),
                "stance": misinfo.get("stance") or output.get("stance") or "",
            }
        )

    return {
        "totals": totals,
        "bands": dict(bands),
        "verdicts": dict(verdicts),
        "stance": dict(stance_dist),
        "latency_ms": {"avg": lat_avg, "p95": lat_p95},
        "risk": {
            "avg": avg_risk,
            "min": (min(risks) if risks else None),
            "max": (max(risks) if risks else None),
        },
        "confidence": {
            "avg": avg_conf,
            "min": (min(confidences) if confidences else None),
            "max": (max(confidences) if confidences else None),
        },
        "timeseries": timeseries[-200:],
        "recent": recent_rows,
        "events_log": str(EVENTS_LOG),
        "generated_at": generated_at,
    }


@app.get("/metrics")
def metrics_alias(window: int = 2000, recent: int = 10, bucket_seconds: int = 60):
    return dashboard_metrics(window=window, recent=recent, bucket_seconds=bucket_seconds)

@app.get("/live-feed")
def live_feed(limit: int = 20):
    return get_live_feed(limit=limit)
# ml/api/metrics_service.py
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# -----------------------------
# Utilities
# -----------------------------
def _now_iso() -> str:
    # lightweight ISO-ish timestamp (UTC epoch used for charting)
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _safe_float(x: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        if x is None:
            return default
        return float(x)
    except Exception:
        return default


def _percentile(sorted_vals: List[float], p: float) -> Optional[float]:
    if not sorted_vals:
        return None
    if p <= 0:
        return float(sorted_vals[0])
    if p >= 100:
        return float(sorted_vals[-1])
    k = (len(sorted_vals) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    if f == c:
        return float(sorted_vals[f])
    d0 = sorted_vals[f] * (c - k)
    d1 = sorted_vals[c] * (k - f)
    return float(d0 + d1)


def _preview_text(input_payload: Any, max_len: int = 120) -> str:
    text = ""
    if isinstance(input_payload, dict):
        t = input_payload.get("text") or input_payload.get("source_text") or ""
        if isinstance(t, str):
            text = t.strip()
    if not text:
        return ""
    return (text[: max_len - 1] + "…") if len(text) > max_len else text


def _read_last_lines(path: Path, max_lines: int) -> List[str]:
    """
    Efficient-ish tail reader. Reads whole file if small; otherwise reads chunks from end.
    """
    if not path.exists():
        return []

    # Small file shortcut
    try:
        size = path.stat().st_size
    except Exception:
        size = 0

    if size < 2_000_000:  # < ~2MB
        try:
            return path.read_text(encoding="utf-8", errors="ignore").splitlines()[-max_lines:]
        except Exception:
            return []

    # Tail from end for larger files
    lines: List[str] = []
    block = 64 * 1024
    with path.open("rb") as f:
        f.seek(0, 2)
        end = f.tell()
        pos = end
        buf = b""
        while pos > 0 and len(lines) < max_lines:
            read_size = min(block, pos)
            pos -= read_size
            f.seek(pos)
            chunk = f.read(read_size)
            buf = chunk + buf
            if b"\n" in chunk:
                parts = buf.split(b"\n")
                # keep first partial in buf
                buf = parts[0]
                for p in parts[1:]:
                    if p.strip():
                        lines.append(p.decode("utf-8", errors="ignore"))
                        if len(lines) >= max_lines:
                            break
        lines.reverse()
    return lines[-max_lines:]


def _parse_event(line: str) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(line)
    except Exception:
        return None


# -----------------------------
# Extract fields from logged event payloads
# -----------------------------
def _get_ts_epoch(ev: Dict[str, Any]) -> Optional[float]:
    # Your log_event may store ts in different keys. Try common ones.
    for k in ("ts", "timestamp", "time", "created_at", "createdAt"):
        v = ev.get(k)
        if isinstance(v, (int, float)):
            return float(v)
    # Sometimes stored as ISO. If so, fallback: not parsing (keep None).
    return None


def _extract_output(ev: Dict[str, Any]) -> Dict[str, Any]:
    out = ev.get("output_payload")
    return out if isinstance(out, dict) else {}


def _extract_input(ev: Dict[str, Any]) -> Dict[str, Any]:
    inp = ev.get("input_payload")
    return inp if isinstance(inp, dict) else {}


def _extract_latency_ms(ev: Dict[str, Any]) -> Optional[float]:
    # If you later log timings, this will pick them up.
    for k in ("latency_ms", "duration_ms", "elapsed_ms", "ms"):
        v = ev.get(k)
        if v is not None:
            return _safe_float(v)
    # Sometimes nested
    meta = ev.get("meta")
    if isinstance(meta, dict):
        for k in ("latency_ms", "duration_ms", "elapsed_ms"):
            v = meta.get(k)
            if v is not None:
                return _safe_float(v)
    return None


def _extract_core_fields(out: Dict[str, Any]) -> Dict[str, Any]:
    risk_band = out.get("risk_band")
    verdict = out.get("action_verdict")
    prob = _safe_float(out.get("misinfo_probability"), None)
    conf = _safe_float(out.get("confidence"), None)

    stance = None
    misinfo = out.get("misinformation")
    if isinstance(misinfo, dict):
        stance = misinfo.get("stance")

    input_type = out.get("input_type")
    req_id = out.get("request_id")

    return {
        "request_id": req_id,
        "risk_band": risk_band,
        "verdict": verdict,
        "misinfo_probability": prob,
        "confidence": conf,
        "stance": stance,
        "input_type": input_type,
    }


# -----------------------------
# Metrics builder
# -----------------------------
def build_metrics(
    *,
    events_log: Path,
    window: int = 2000,          # number of recent events to scan
    recent: int = 10,            # number of recent items to return
    bucket_seconds: int = 60,    # chart granularity
) -> Dict[str, Any]:
    """
    Reads the last `window` events from JSONL and returns aggregated metrics + timeseries.
    Designed for dashboard polling.
    """
    lines = _read_last_lines(events_log, max_lines=window)
    events: List[Dict[str, Any]] = []

    for line in lines:
        ev = _parse_event(line)
        if ev:
            events.append(ev)

    totals = {
        "events_scanned": len(events),
        "analyses": 0,
        "errors": 0,
    }

    bands = {"LOW": 0, "MEDIUM": 0, "HIGH": 0}
    verdicts = {"SAFE_TO_SHARE": 0, "VERIFY_REQUIRED": 0, "LIKELY_MISINFORMATION": 0}
    stance = {"debunking": 0, "warning": 0, "neutral": 0, "spreading": 0, "unknown": 0}

    probs: List[float] = []
    confs: List[float] = []
    latencies: List[float] = []

    # timeseries bucket -> accumulators
    # key: bucket_start_epoch -> dict
    series: Dict[int, Dict[str, Any]] = {}

    recents: List[Dict[str, Any]] = []

    for ev in events:
        out = _extract_output(ev)
        inp = _extract_input(ev)

        # Only count prediction events
        # Your logger uses event_type="predict"
        event_type = ev.get("event_type")
        if event_type and event_type != "predict":
            continue

        totals["analyses"] += 1

        core = _extract_core_fields(out)
        rb = core["risk_band"] or "UNKNOWN"
        vd = core["verdict"] or "UNKNOWN"
        st = core["stance"] or "unknown"

        if rb in bands:
            bands[rb] += 1

        if vd in verdicts:
            verdicts[vd] += 1

        if st in stance:
            stance[st] += 1
        else:
            stance["unknown"] += 1

        p = core["misinfo_probability"]
        if p is not None:
            probs.append(p)

        c = core["confidence"]
        if c is not None:
            confs.append(c)

        lat = _extract_latency_ms(ev)
        if lat is not None:
            latencies.append(lat)

        # timeseries
        ts = _get_ts_epoch(ev)
        if ts is not None:
            bucket = int(ts // bucket_seconds) * bucket_seconds
            b = series.get(bucket)
            if b is None:
                b = {
                    "t": bucket,
                    "count": 0,
                    "avg_risk_sum": 0.0,
                    "avg_risk_n": 0,
                    "LOW": 0,
                    "MEDIUM": 0,
                    "HIGH": 0,
                }
                series[bucket] = b

            b["count"] += 1
            if rb in ("LOW", "MEDIUM", "HIGH"):
                b[rb] += 1
            if p is not None:
                b["avg_risk_sum"] += float(p)
                b["avg_risk_n"] += 1

        # recent list
        recents.append(
            {
                "request_id": core["request_id"],
                "ts": ts,
                "risk_band": core["risk_band"],
                "verdict": core["verdict"],
                "misinfo_probability": core["misinfo_probability"],
                "confidence": core["confidence"],
                "stance": core["stance"],
                "input_type": core["input_type"],
                "text_preview": _preview_text(inp, max_len=140),
            }
        )

    probs_avg = sum(probs) / len(probs) if probs else None
    conf_avg = sum(confs) / len(confs) if confs else None

    lat_sorted = sorted(latencies)
    lat_avg = sum(lat_sorted) / len(lat_sorted) if lat_sorted else None
    lat_p50 = _percentile(lat_sorted, 50) if lat_sorted else None
    lat_p95 = _percentile(lat_sorted, 95) if lat_sorted else None

    # build ordered timeseries
    ts_items = []
    for bucket in sorted(series.keys()):
        b = series[bucket]
        avg_risk = (b["avg_risk_sum"] / b["avg_risk_n"]) if b["avg_risk_n"] else None
        ts_items.append(
            {
                "t": b["t"],  # epoch seconds
                "count": b["count"],
                "avg_risk": avg_risk,
                "LOW": b["LOW"],
                "MEDIUM": b["MEDIUM"],
                "HIGH": b["HIGH"],
            }
        )

    # recent items (most recent last in file -> make newest first)
    recents_sorted = [r for r in recents if r.get("ts") is not None]
    recents_sorted.sort(key=lambda x: x["ts"], reverse=True)
    recent_items = recents_sorted[: max(0, int(recent))]

    return {
        "generated_at": _now_iso(),
        "window": int(window),
        "bucket_seconds": int(bucket_seconds),
        "totals": totals,
        "bands": bands,
        "verdicts": verdicts,
        "stance": stance,
        "risk": {"avg": probs_avg},
        "confidence": {"avg": conf_avg},
        "latency_ms": {"avg": lat_avg, "p50": lat_p50, "p95": lat_p95},
        "timeseries": ts_items,
        "recent": recent_items,
        "events_log": str(events_log),
    }

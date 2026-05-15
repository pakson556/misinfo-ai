from __future__ import annotations

import json
import os
import re
import ssl
import time
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional


# ---------------------------------
# Generic helpers
# ---------------------------------
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/123.0.0.0 Safari/537.36"
)

GOOGLE_FACTCHECK_ENDPOINT = "https://factchecktools.googleapis.com/v1alpha1/claims:search"

MONITORED_TOPICS = [
    "covid vaccines",
    "vaccines microchips",
    "climate change",
    "global warming hoax",
    "election fraud",
    "postal voting fraud",
    "government policy",
    "immigration policy",
    "refugees misinformation",
    "cost of living",
    "inflation misinformation",
    "tax misinformation",
    "university closures",
    "school closures misinformation",
    "war misinformation",
    "ukraine misinformation",
    "middle east misinformation",
    "crime misinformation",
    "deepfake politics",
    "ai misinformation",
]


def _now_iso() -> str:
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


def _preview_text(input_payload: Any, max_len: int = 140) -> str:
    text = ""
    if isinstance(input_payload, dict):
        t = input_payload.get("text") or input_payload.get("source_text") or ""
        if isinstance(t, str):
            text = t.strip()

    if not text:
        return ""

    return (text[: max_len - 1] + "…") if len(text) > max_len else text


def _read_last_lines(path: Path, max_lines: int) -> List[str]:
    if not path.exists():
        return []

    try:
        size = path.stat().st_size
    except Exception:
        size = 0

    if size < 2_000_000:
        try:
            return path.read_text(encoding="utf-8", errors="ignore").splitlines()[-max_lines:]
        except Exception:
            return []

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


def _extract_output(ev: Dict[str, Any]) -> Dict[str, Any]:
    out = ev.get("output_payload")
    if isinstance(out, dict):
        return out

    out = ev.get("output")
    if isinstance(out, dict):
        return out

    return {}


def _extract_input(ev: Dict[str, Any]) -> Dict[str, Any]:
    inp = ev.get("input_payload")
    if isinstance(inp, dict):
        return inp

    inp = ev.get("input")
    if isinstance(inp, dict):
        return inp

    return {}


def _extract_latency_ms(ev: Dict[str, Any]) -> Optional[float]:
    for k in ("latency_ms", "duration_ms", "elapsed_ms", "ms"):
        v = ev.get(k)
        if v is not None:
            return _safe_float(v)

    meta = ev.get("meta")
    if isinstance(meta, dict):
        for k in ("latency_ms", "duration_ms", "elapsed_ms"):
            v = meta.get(k)
            if v is not None:
                return _safe_float(v)

    return None


def _get_ts_epoch(ev: Dict[str, Any], index: int = 0) -> Optional[float]:
    for k in ("ts_epoch", "timestamp_epoch", "time_epoch"):
        v = ev.get(k)
        if isinstance(v, (int, float)):
            return float(v)

    for k in ("ts", "timestamp", "time", "created_at", "createdAt"):
        v = ev.get(k)
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str):
            try:
                return float(
                    time.mktime(time.strptime(v[:19], "%Y-%m-%dT%H:%M:%S"))
                )
            except Exception:
                pass

    return float(index)


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
    internet = out.get("internet_verification") if isinstance(out.get("internet_verification"), dict) else {}

    return {
        "request_id": req_id,
        "risk_band": risk_band,
        "verdict": verdict,
        "misinfo_probability": prob,
        "confidence": conf,
        "stance": stance,
        "input_type": input_type,
        "internet_verification": internet,
    }


# ---------------------------------
# Dashboard metrics builder
# ---------------------------------
def build_metrics(
    *,
    events_log: Path,
    window: int = 2000,
    recent: int = 10,
    bucket_seconds: int = 60,
) -> Dict[str, Any]:
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
    series: Dict[int, Dict[str, Any]] = {}
    recents: List[Dict[str, Any]] = []

    for idx, ev in enumerate(events):
        out = _extract_output(ev)
        inp = _extract_input(ev)

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

        ts = _get_ts_epoch(ev, idx)
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

    ts_items = []
    for bucket in sorted(series.keys()):
        b = series[bucket]
        avg_risk = (b["avg_risk_sum"] / b["avg_risk_n"]) if b["avg_risk_n"] else None
        ts_items.append(
            {
                "t": b["t"],
                "count": b["count"],
                "avg_risk": avg_risk,
                "LOW": b["LOW"],
                "MEDIUM": b["MEDIUM"],
                "HIGH": b["HIGH"],
            }
        )

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
        "recent_items": recent_items,
    }


# ---------------------------------
# Global monitor logic
# ---------------------------------
STOP_WORDS = {
    "the", "and", "that", "this", "with", "from", "they", "them", "their", "there",
    "have", "has", "had", "been", "were", "was", "are", "for", "into", "about",
    "your", "yours", "will", "would", "could", "should", "after", "before", "because",
    "while", "where", "which", "what", "when", "then", "than", "into", "over",
    "under", "again", "very", "just", "more", "most", "some", "such", "many",
    "also", "only", "like", "look", "even", "well", "much", "make", "made", "does",
    "did", "dont", "doesnt", "isnt", "arent", "cant", "cannot", "wont", "wouldnt",
    "shouldnt", "might", "must", "need", "know", "says", "said", "using", "used",
    "through", "being", "each", "other", "those", "these", "across",
    "here", "there", "still", "really", "text", "content",
    "claim", "claims", "appears", "appear", "show", "shows", "showing", "report",
    "reports", "reported", "information", "people", "general", "public",
    "false", "true", "likely", "required", "safe", "share", "trust", "without",
    "strong", "high", "low", "medium", "risk", "signal", "analysis", "model",
    "models", "confidence", "probability", "misinformation", "verify", "verified",
    "unverified", "internet", "evidence", "source", "sources",
}

CATEGORY_TERMS = {
    "health": {
        "covid", "vaccine", "vaccines", "virus", "mask", "masks", "patient",
        "patients", "doctor", "hospital", "treatment", "cure", "infection",
        "symptoms", "health", "medical", "microchips", "booster", "pandemic",
    },
    "science": {
        "study", "studies", "research", "data", "scientists", "science",
        "evidence", "results", "brain", "nasa", "climate", "warming",
        "emissions", "temperature", "temperatures", "carbon",
    },
    "politics": {
        "government", "president", "prime", "minister", "parliament", "senate",
        "congress", "democracy", "political", "party", "leader", "state",
        "regime", "policy", "policies", "law", "laws", "cabinet", "mp",
    },
    "elections": {
        "election", "elections", "vote", "voter", "ballot", "polling",
        "polls", "campaign", "candidate", "rigged", "fraud",
    },
    "economy": {
        "economy", "economic", "inflation", "tax", "taxes", "budget",
        "markets", "market", "trade", "jobs", "salary", "wages",
        "oil", "energy", "cost", "prices", "recession", "rent",
    },
    "security": {
        "war", "military", "army", "cyber", "security", "attack", "missile",
        "nuclear", "weapons", "terror", "surveillance", "hack", "breach",
        "conflict", "troops",
    },
    "education": {
        "school", "schools", "university", "universities", "student", "students",
        "teacher", "teachers", "tuition", "education", "degree",
        "campus", "course",
    },
    "media": {
        "media", "headline", "article", "reporting", "news", "press", "viral",
        "journalist", "broadcast",
    },
    "technology": {
        "ai", "chatgpt", "algorithm", "technology", "system", "robot",
        "automation", "deepfake", "software", "platform",
    },
    "migration": {
        "immigration", "immigrant", "immigrants", "migrant", "migrants",
        "border", "asylum", "refugee", "refugees", "deportation",
    },
    "crime": {
        "crime", "criminal", "police", "arrest", "murder", "theft",
        "violence", "gang", "assault", "fraudulent",
    },
    "misinformation": {
        "hoax", "fake", "myth", "conspiracy", "misleading", "debunked",
        "falsehood", "propaganda", "scam", "deepfake",
    },
    "other": set(),
}

NARRATIVE_PATTERNS = {
    "Health misinformation": {
        "covid", "vaccine", "vaccines", "mask", "masks", "hospital", "doctor",
        "virus", "cure", "microchips", "booster",
    },
    "Science myths": {
        "brain", "research", "study", "studies", "scientists", "evidence",
        "climate", "warming", "temperature", "carbon",
    },
    "Political misinformation": {
        "government", "president", "minister", "parliament", "policy",
        "political", "party", "law", "laws", "democracy",
    },
    "Election misinformation": {
        "election", "vote", "voter", "ballot", "candidate", "rigged", "fraud",
        "polling",
    },
    "Economic misinformation": {
        "economy", "inflation", "tax", "budget", "market", "trade",
        "jobs", "wages", "prices", "recession", "rent",
    },
    "Security narratives": {
        "war", "military", "cyber", "attack", "missile", "nuclear",
        "weapons", "hack", "breach", "conflict",
    },
    "Education panic": {
        "school", "schools", "university", "universities", "student",
        "teacher", "education", "tuition", "campus",
    },
    "Migration narratives": {
        "immigration", "immigrant", "immigrants", "migrant", "migrants",
        "border", "asylum", "refugee", "refugees",
    },
    "Crime panic": {
        "crime", "criminal", "police", "violence", "gang", "assault", "murder",
    },
    "Media manipulation": {
        "media", "news", "headline", "article", "reporting", "viral", "broadcast",
    },
    "Technology fear": {
        "ai", "chatgpt", "algorithm", "technology", "robot", "automation", "deepfake",
    },
    "Conspiracy narratives": {
        "conspiracy", "hoax", "secret", "agenda", "fake", "deepfake", "propaganda",
    },
}


def _extract_text(ev: Dict[str, Any]) -> str:
    inp = _extract_input(ev)
    if not inp:
        return ""
    text = inp.get("text") or inp.get("source_text") or ""
    return text.strip() if isinstance(text, str) else ""


def _extract_triggers(ev: Dict[str, Any]) -> List[Dict[str, Any]]:
    out = _extract_output(ev)
    triggers = out.get("triggers")
    return triggers if isinstance(triggers, list) else []


def _extract_internet_verdict(ev: Dict[str, Any]) -> str:
    out = _extract_output(ev)
    internet = out.get("internet_verification")
    if isinstance(internet, dict):
        return str(internet.get("overall_verdict", "UNVERIFIED")).upper()
    return "UNVERIFIED"


def _extract_event_summary(ev: Dict[str, Any], idx: int) -> Dict[str, Any]:
    out = _extract_output(ev)
    core = _extract_core_fields(out)
    return {
        "ts": _get_ts_epoch(ev, idx),
        "text": _extract_text(ev),
        "request_id": core["request_id"],
        "verdict": core["verdict"] or "UNKNOWN",
        "risk_band": core["risk_band"] or "UNKNOWN",
        "misinfo_probability": float(core["misinfo_probability"] or 0.0),
        "confidence": float(core["confidence"] or 0.0),
        "internet_overall_verdict": _extract_internet_verdict(ev),
        "triggers": _extract_triggers(ev),
    }


def _tokenize_text(text: str) -> List[str]:
    return re.findall(r"[a-zA-Z][a-zA-Z0-9'-]{2,}", (text or "").lower())


def _meaningful_terms(text: str) -> List[str]:
    terms = []
    for tok in _tokenize_text(text):
        if tok in STOP_WORDS:
            continue
        if len(tok) < 3:
            continue
        terms.append(tok)
    return terms


def _categorize_term(term: str) -> str:
    tl = term.lower()
    for category, words in CATEGORY_TERMS.items():
        if tl in words:
            return category
    return "other"


def _trend_direction(prev_count: int, current_count: int) -> str:
    if prev_count <= 0 and current_count > 0:
        return "new"
    if prev_count <= 0:
        return "stable"

    delta = (current_count - prev_count) / max(1, prev_count)
    if delta >= 0.20:
        return "rising"
    if delta <= -0.20:
        return "falling"
    return "stable"


def _risk_level(avg_prob: float) -> str:
    if avg_prob >= 0.65:
        return "HIGH"
    if avg_prob >= 0.35:
        return "MEDIUM"
    return "LOW"


def _is_high_risk_event(ev: Dict[str, Any]) -> bool:
    prob = float(ev.get("misinfo_probability", 0.0))
    verdict = str(ev.get("verdict", "")).upper()
    internet = str(ev.get("internet_overall_verdict", "UNVERIFIED")).upper()
    risk_band = str(ev.get("risk_band", "")).upper()

    if internet == "LIKELY_FALSE":
        return True

    if verdict == "LIKELY_MISINFORMATION":
        return True

    if risk_band == "HIGH" and prob >= 0.45:
        return True

    return False


def _normalize_claim(text: str) -> str:
    text = (text or "").strip().lower()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[\"'`]+", "", text)
    return text


def _display_claim(text: str, max_len: int = 90) -> str:
    text = (text or "").strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


def _detect_claim_category(text: str) -> str:
    terms = set(_meaningful_terms(text))
    scores: Dict[str, int] = {}

    for category, words in CATEGORY_TERMS.items():
        overlap = len(terms.intersection(words))
        if overlap > 0:
            scores[category] = overlap

    if not scores:
        return "other"

    return max(scores.items(), key=lambda x: x[1])[0]


def _build_term_stats(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not events:
        return []

    split_idx = max(1, len(events) // 2)
    prev_events = events[:split_idx]
    current_events = events[split_idx:]

    current_counts: Dict[str, int] = {}
    previous_counts: Dict[str, int] = {}
    term_risk_sum: Dict[str, float] = {}
    term_event_count: Dict[str, int] = {}
    term_last_seen: Dict[str, float] = {}

    def add_term(store: Dict[str, int], term: str) -> None:
        store[term] = store.get(term, 0) + 1

    for ev in prev_events:
        for term in set(_meaningful_terms(ev.get("text", ""))):
            add_term(previous_counts, term)

    for ev in current_events:
        terms = set(_meaningful_terms(ev.get("text", "")))
        prob = float(ev.get("misinfo_probability", 0.0))
        ts = float(ev.get("ts", 0.0) or 0.0)

        for term in terms:
            add_term(current_counts, term)
            term_risk_sum[term] = term_risk_sum.get(term, 0.0) + prob
            term_event_count[term] = term_event_count.get(term, 0) + 1
            term_last_seen[term] = max(term_last_seen.get(term, 0.0), ts)

    all_terms = set(previous_counts.keys()) | set(current_counts.keys())
    results: List[Dict[str, Any]] = []

    for term in all_terms:
        count = current_counts.get(term, 0)
        prev_count = previous_counts.get(term, 0)
        avg_prob = term_risk_sum.get(term, 0.0) / max(1, term_event_count.get(term, 1))

        results.append(
            {
                "term": term,
                "count": count,
                "prev_count": prev_count,
                "trend": _trend_direction(prev_count, count),
                "risk_level": _risk_level(avg_prob),
                "avg_risk": round(avg_prob, 4),
                "category": _categorize_term(term),
                "last_seen": term_last_seen.get(term, 0.0),
            }
        )

    results.sort(key=lambda x: (x["count"], x["avg_risk"]), reverse=True)
    return results


def _build_trending_claims(events: List[Dict[str, Any]], limit: int = 8) -> List[Dict[str, Any]]:
    if not events:
        return []

    filtered_events = []
    for ev in events:
        prob = float(ev.get("misinfo_probability", 0.0))
        verdict = str(ev.get("verdict", "")).upper()
        internet = str(ev.get("internet_overall_verdict", "UNVERIFIED")).upper()
        risk_band = str(ev.get("risk_band", "")).upper()

        include = (
            internet == "LIKELY_FALSE"
            or verdict == "LIKELY_MISINFORMATION"
            or (risk_band == "HIGH" and prob >= 0.45)
        )

        if include:
            filtered_events.append(ev)

    if not filtered_events:
        return []

    split_idx = max(1, len(filtered_events) // 2)
    prev_events = filtered_events[:split_idx]
    current_events = filtered_events[split_idx:]

    prev_counter = Counter(
        _normalize_claim(ev.get("text", "")) for ev in prev_events if ev.get("text")
    )
    current_counter = Counter(
        _normalize_claim(ev.get("text", "")) for ev in current_events if ev.get("text")
    )

    claim_stats: Dict[str, Dict[str, Any]] = {}

    for ev in filtered_events:
        raw_text = ev.get("text", "")
        norm = _normalize_claim(raw_text)
        if not norm:
            continue

        item = claim_stats.get(norm)
        if item is None:
            item = {
                "claim": _display_claim(raw_text, 100),
                "count_total": 0,
                "avg_risk_sum": 0.0,
                "avg_risk_n": 0,
                "category": _detect_claim_category(raw_text),
                "internet_false_hits": 0,
                "verdict_hits": 0,
            }
            claim_stats[norm] = item

        item["count_total"] += 1
        item["avg_risk_sum"] += float(ev.get("misinfo_probability", 0.0))
        item["avg_risk_n"] += 1

        if str(ev.get("internet_overall_verdict", "UNVERIFIED")).upper() == "LIKELY_FALSE":
            item["internet_false_hits"] += 1

        if str(ev.get("verdict", "")).upper() == "LIKELY_MISINFORMATION":
            item["verdict_hits"] += 1

    rows: List[Dict[str, Any]] = []
    for norm, stats in claim_stats.items():
        current_count = current_counter.get(norm, 0)
        prev_count = prev_counter.get(norm, 0)
        total_count = stats["count_total"]
        avg_risk = stats["avg_risk_sum"] / max(1, stats["avg_risk_n"])

        trend_score = total_count * avg_risk * (1.25 if stats["internet_false_hits"] > 0 else 1.0)

        rows.append(
            {
                "claim": stats["claim"],
                "count": current_count if current_count > 0 else total_count,
                "prev_count": prev_count,
                "trend": _trend_direction(prev_count, current_count if current_count > 0 else total_count),
                "avg_risk": round(avg_risk, 4),
                "risk_level": _risk_level(avg_risk),
                "category": stats["category"],
                "internet_false_hits": stats["internet_false_hits"],
                "verdict_hits": stats["verdict_hits"],
                "trend_score": round(trend_score, 4),
            }
        )

    rows.sort(
        key=lambda x: (
            x["trend_score"],
            x["internet_false_hits"],
            x["verdict_hits"],
            x["count"],
        ),
        reverse=True,
    )
    return rows[:limit]


def _build_narratives(events: List[Dict[str, Any]], limit: int = 6) -> List[Dict[str, Any]]:
    narratives: List[Dict[str, Any]] = []

    for label, keywords in NARRATIVE_PATTERNS.items():
        matched_events = []
        for ev in events:
            text_terms = set(_meaningful_terms(ev.get("text", "")))
            overlap = text_terms.intersection(keywords)
            if overlap:
                matched_events.append((ev, overlap))

        if not matched_events:
            continue

        total_mentions = len(matched_events)
        avg_risk = sum(float(ev["misinfo_probability"]) for ev, _ in matched_events) / max(1, total_mentions)
        example_text = matched_events[-1][0].get("text", "")
        top_keywords: Dict[str, int] = {}

        for _, overlap in matched_events:
            for kw in overlap:
                top_keywords[kw] = top_keywords.get(kw, 0) + 1

        sorted_kws = sorted(top_keywords.items(), key=lambda x: x[1], reverse=True)
        narratives.append(
            {
                "label": label,
                "mentions": total_mentions,
                "avg_risk": round(avg_risk, 4),
                "risk_level": _risk_level(avg_risk),
                "keywords": [kw for kw, _ in sorted_kws[:4]],
                "example_text": _display_claim(example_text, 160),
            }
        )

    narratives.sort(key=lambda x: (x["mentions"], x["avg_risk"]), reverse=True)
    return narratives[:limit]


def _build_recent_high_risk(events: List[Dict[str, Any]], limit: int = 6) -> List[Dict[str, Any]]:
    high_risk = [ev for ev in events if _is_high_risk_event(ev)]
    high_risk.sort(key=lambda x: x.get("ts", 0.0), reverse=True)

    items = []
    seen_claims = set()

    for ev in high_risk:
        raw_text = ev.get("text", "")
        normalized = _normalize_claim(raw_text)

        if not normalized or normalized in seen_claims:
            continue
        seen_claims.add(normalized)

        top_trigger = None
        triggers = ev.get("triggers", [])
        if triggers:
            first = triggers[0]
            top_trigger = first.get("name") or first.get("explanation")

        items.append(
            {
                "request_id": ev.get("request_id"),
                "text": _display_claim(raw_text, 220),
                "misinfo_probability": round(float(ev.get("misinfo_probability", 0.0)), 4),
                "confidence": round(float(ev.get("confidence", 0.0)), 4),
                "risk_band": ev.get("risk_band", "UNKNOWN"),
                "verdict": ev.get("verdict", "UNKNOWN"),
                "internet_overall_verdict": ev.get("internet_overall_verdict", "UNVERIFIED"),
                "top_trigger": top_trigger,
            }
        )

        if len(items) >= limit:
            break

    return items


# ---------------------------------
# External live feed (Google Fact Check API)
# ---------------------------------
def _google_factcheck_api_key() -> str:
    return (
        os.getenv("GOOGLE_FACTCHECK_API_KEY", "").strip()
        or os.getenv("FACTCHECK_API_KEY", "").strip()
    )


def _safe_get_json(url: str, timeout: int = 15) -> Dict[str, Any]:
    ctx = ssl.create_default_context()
    req = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        return json.loads(resp.read().decode("utf-8", errors="ignore"))


def _factcheck_rating_to_risk(textual_rating: str) -> float:
    rating = (textual_rating or "").strip().lower()

    if any(x in rating for x in ["false", "fake", "hoax", "misleading", "myth", "incorrect", "pants on fire"]):
        return 0.90
    if any(x in rating for x in ["partly false", "partially false", "missing context", "out of context", "mixed"]):
        return 0.60
    if any(x in rating for x in ["true", "correct", "accurate", "mostly true"]):
        return 0.10

    return 0.35


def _factcheck_rating_to_label(textual_rating: str) -> str:
    rating = (textual_rating or "").strip().lower()

    if any(x in rating for x in ["false", "fake", "hoax", "misleading", "myth", "incorrect", "pants on fire"]):
        return "LIKELY_FALSE"
    if any(x in rating for x in ["partly false", "partially false", "missing context", "out of context", "mixed"]):
        return "MIXED"
    if any(x in rating for x in ["true", "correct", "accurate", "mostly true"]):
        return "LIKELY_TRUE"

    return "UNVERIFIED"


def _fetch_factcheck_topic(topic: str, language_code: str = "en", page_size: int = 5) -> List[Dict[str, Any]]:
    api_key = _google_factcheck_api_key()
    if not api_key:
        return []

    params = {
        "query": topic,
        "languageCode": language_code,
        "pageSize": page_size,
        "key": api_key,
    }

    url = f"{GOOGLE_FACTCHECK_ENDPOINT}?{urllib.parse.urlencode(params)}"

    try:
        payload = _safe_get_json(url)
    except Exception:
        return []

    claims = payload.get("claims", []) or []
    items: List[Dict[str, Any]] = []

    for claim in claims:
        claim_text = claim.get("text", "") or topic
        reviews = claim.get("claimReview", []) or []

        for review in reviews:
            publisher = review.get("publisher", {}) or {}
            publisher_name = publisher.get("name", "") or "Unknown publisher"
            review_url = review.get("url", "") or ""
            title = review.get("title", "") or claim_text
            textual_rating = review.get("textualRating", "") or ""
            review_date = review.get("reviewDate", "") or ""
            verdict = _factcheck_rating_to_label(textual_rating)
            risk = _factcheck_rating_to_risk(textual_rating)

            items.append(
                {
                    "topic": topic,
                    "claim": claim_text,
                    "title": title,
                    "publisher": publisher_name,
                    "url": review_url,
                    "textual_rating": textual_rating,
                    "verdict": verdict,
                    "risk": round(risk, 4),
                    "review_date": review_date,
                }
            )

    return items


def build_live_external_feed(limit: int = 15) -> Dict[str, Any]:
    all_items: List[Dict[str, Any]] = []
    seen = set()

    for topic in MONITORED_TOPICS:
        rows = _fetch_factcheck_topic(topic, page_size=5)
        for row in rows:
            key = (
                row.get("claim", "").strip().lower(),
                row.get("publisher", "").strip().lower(),
            )
            if key in seen:
                continue
            seen.add(key)
            all_items.append(row)

    all_items.sort(
        key=lambda x: (
            x.get("risk", 0.0),
            x.get("review_date", ""),
        ),
        reverse=True,
    )

    return {
        "generated_at": _now_iso(),
        "source": "google_factcheck_api",
        "topics": MONITORED_TOPICS,
        "items": all_items[:limit],
    }


def build_global_monitor(
    *,
    events_log: Path,
    limit: int = 20,
    window: int = 2000,
) -> Dict[str, Any]:
    lines = _read_last_lines(events_log, max_lines=window)
    raw_events: List[Dict[str, Any]] = []

    for line in lines:
        ev = _parse_event(line)
        if not ev:
            continue
        event_type = ev.get("event_type")
        if event_type and event_type != "predict":
            continue
        raw_events.append(ev)

    events = [_extract_event_summary(ev, idx) for idx, ev in enumerate(raw_events)]
    events = [ev for ev in events if ev.get("text")]

    term_stats = _build_term_stats(events)
    top_terms = term_stats[: max(1, int(limit))]

    high_risk_events = [ev for ev in events if _is_high_risk_event(ev)]
    trending_misinformation = _build_trending_claims(high_risk_events, limit=8)
    narratives = _build_narratives(high_risk_events, limit=6)
    recent_high_risk = _build_recent_high_risk(events, limit=6)

    category_counts: Dict[str, int] = {}
    for item in top_terms:
        cat = item.get("category", "other")
        category_counts[cat] = category_counts.get(cat, 0) + 1

    avg_risk = (
        sum(float(ev.get("misinfo_probability", 0.0)) for ev in events) / max(1, len(events))
        if events else 0.0
    )
    avg_high_risk = (
        sum(float(ev.get("misinfo_probability", 0.0)) for ev in high_risk_events) / max(1, len(high_risk_events))
        if high_risk_events else 0.0
    )

    threat_level = _risk_level(avg_high_risk if high_risk_events else avg_risk)

    return {
        "generated_at": _now_iso(),
        "window": int(window),
        "total_events": len(events),
        "misinfo_events": len(high_risk_events),
        "total_terms": len(top_terms),
        "avg_risk": round(avg_risk, 4),
        "avg_high_risk": round(avg_high_risk, 4),
        "threat_level": threat_level,
        "category_counts": category_counts,
        "top_terms": top_terms,
        "terms": top_terms,
        "trending_misinformation": trending_misinformation,
        "narratives": narratives,
        "recent_high_risk": recent_high_risk,
    }
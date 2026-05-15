from __future__ import annotations

import json
import re
import ssl
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Dict, List, Optional

import feedparser

USER_AGENT = "Mozilla/5.0"
HEADERS = {"User-Agent": USER_AGENT}

GOOGLE_NEWS_QUERY = (
    "misinformation OR disinformation OR debunked OR fact-check OR "
    "\"false claim\" OR \"false claims\" OR deepfake OR \"out of context\" OR "
    "\"manipulated video\" OR \"manipulated image\" OR conspiracy"
)

GOOGLE_NEWS_URL = (
    "https://news.google.com/rss/search?"
    + urllib.parse.urlencode(
        {
            "q": GOOGLE_NEWS_QUERY,
            "hl": "en-GB",
            "gl": "GB",
            "ceid": "GB:en",
        }
    )
)

BBC_NEWS_URL = "https://feeds.bbci.co.uk/news/rss.xml"
REUTERS_NEWS_URL = "https://feeds.reuters.com/reuters/topNews"

# Reddit kept here in case you enable API-based integration later.
REDDIT_URLS = [
    "https://www.reddit.com/r/conspiracy/.json?limit=25",
    "https://www.reddit.com/r/worldnews/.json?limit=25",
    "https://www.reddit.com/r/politics/.json?limit=25",
    "https://www.reddit.com/r/news/.json?limit=25",
]

MISINFO_WORDING = {
    "misinformation",
    "disinformation",
    "false claim",
    "false claims",
    "debunked",
    "fact check",
    "fact-check",
    "conspiracy theory",
    "deepfake",
    "fabricated story",
    "manipulated video",
    "manipulated image",
    "misleading post",
    "misleading video",
    "misleading image",
    "misleading claim",
    "viral hoax",
    "online hoax",
    "false narrative",
    "out of context",
    "doctored video",
    "doctored image",
    "shared falsely",
    "falsely claimed",
    "circulating online",
    "viral claim",
    "fact-checkers",
    "debunking",
}

SOCIAL_MISINFO_HINTS = {
    "viral",
    "circulating",
    "shared",
    "spread online",
    "posted on x",
    "posted on facebook",
    "posted on instagram",
    "posted on tiktok",
    "reddit post",
    "social media",
    "users claimed",
    "false post",
    "online claim",
}

FACTCHECK_HINTS = {
    "debunked",
    "fact check",
    "fact-check",
    "fact-checkers",
    "false claim",
    "false claims",
    "falsely claimed",
    "out of context",
    "debunking",
}

MANIPULATED_MEDIA_HINTS = {
    "deepfake",
    "manipulated video",
    "manipulated image",
    "doctored video",
    "doctored image",
    "ai-generated",
    "edited clip",
}

TOPIC_KEYWORDS = {
    "health": {
        "covid", "vaccine", "vaccines", "virus", "booster", "pandemic",
        "mask", "health", "medical", "hospital", "fertility",
    },
    "politics": {
        "government", "minister", "president", "prime minister", "parliament",
        "policy", "politics", "political", "law", "laws", "starmer", "trump",
        "biden", "rfk", "netanyahu",
    },
    "elections": {
        "election", "elections", "vote", "voter", "ballot", "poll",
        "polling", "candidate", "fraud", "rigged",
    },
    "war": {
        "war", "missile", "attack", "troops", "ukraine", "russia",
        "gaza", "israel", "iran", "military", "ceasefire", "conflict",
        "air strike", "airstrike",
    },
    "technology": {
        "ai", "artificial intelligence", "deepfake", "chatgpt",
        "algorithm", "technology", "platform", "social media",
        "tiktok", "youtube", "instagram", "twitter", "x ",
    },
    "climate": {
        "climate", "global warming", "carbon", "emissions",
        "temperature", "temperatures", "weather",
    },
    "economy": {
        "economy", "inflation", "prices", "cost of living",
        "recession", "energy", "tax", "budget",
    },
    "migration": {
        "immigration", "immigrant", "immigrants", "migrant", "migrants",
        "border", "asylum", "refugee", "refugees",
    },
    "crime": {
        "crime", "fraud", "scam", "police", "criminal",
        "arrest", "gang", "violence",
    },
}

BAD_FALSE_POSITIVES = {
    "fake gun",
    "fake police",
    "fake bank",
    "fake banks",
    "fake review",
    "fake reviews",
    "fake passport",
    "fake id",
    "fake ids",
    "scam compound",
    "misleading reviews",
    "misleading advertising",
    "fraud investigation",
    "consumer review",
    "police station",
    "jailed for threatening",
    "worker with fake gun",
    "inside a scammer compound",
    "fake police stations",
    "banks inside a scammer compound",
    "misleading customers",
    "misleading business practice",
    "business reviews",
}

SOURCE_CREDIBILITY = {
    "BBC": 0.95,
    "Reuters": 0.96,
    "Google News": 0.82,
    "Reddit": 0.55,
}


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _fetch_text(url: str, timeout: int = 15) -> str:
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, headers=HEADERS, method="GET")
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def _fetch_json(url: str, timeout: int = 15) -> Dict[str, Any]:
    return json.loads(_fetch_text(url, timeout=timeout))


def _clean_text(text: Optional[str]) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("&amp;", "&")
    text = text.replace("&#39;", "'")
    text = text.replace("&quot;", '"')
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _to_epoch(value: Optional[str]) -> Optional[float]:
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except Exception:
        return None


def _published_iso(value: Optional[str]) -> str:
    epoch = _to_epoch(value)
    if epoch is None:
        return ""
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _contains_misinfo_wording(text: str) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in MISINFO_WORDING)


def _contains_social_hint(text: str) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in SOCIAL_MISINFO_HINTS)


def _matched_terms(text: str, vocabulary: set[str]) -> List[str]:
    lowered = text.lower()
    found = [term for term in vocabulary if term in lowered]
    found.sort(key=len, reverse=True)
    return found


def _wording_hits(text: str) -> int:
    return len(_matched_terms(text, MISINFO_WORDING))


def _infer_topic(text: str) -> str:
    lowered = text.lower()
    best_topic = "other"
    best_score = 0

    for topic, words in TOPIC_KEYWORDS.items():
        score = sum(1 for w in words if w in lowered)
        if score > best_score:
            best_score = score
            best_topic = topic

    return best_topic


def _source_credibility(source: str) -> float:
    return SOURCE_CREDIBILITY.get(source, 0.70)


def _is_bad_false_positive(text: str) -> bool:
    lowered = text.lower()
    return any(p in lowered for p in BAD_FALSE_POSITIVES)


def _risk_from_text(text: str, source: str, engagement: Optional[int] = None) -> float:
    hits = _wording_hits(text)
    risk = 0.22

    if source == "Google News":
        risk += 0.08
    elif source == "BBC":
        risk += 0.05
    elif source == "Reuters":
        risk += 0.05
    elif source == "Reddit":
        risk += 0.18

    risk += min(0.28, hits * 0.07)

    if _contains_social_hint(text):
        risk += 0.08

    if source == "Reddit" and engagement:
        risk += min(0.15, float(engagement) / 4000.0)

    return max(0.10, min(0.95, risk))


def _signal_type(source: str, engagement: Optional[int], risk: float) -> str:
    if source == "Reddit":
        if engagement and engagement >= 1000:
            return "SOCIAL SURGE"
        return "SOCIAL SIGNAL"
    if risk >= 0.65:
        return "HIGH PRIORITY"
    return "NEWS SIGNAL"


def _signal_strength(risk: float) -> str:
    if risk >= 0.65:
        return "HIGH"
    if risk >= 0.35:
        return "MEDIUM"
    return "LOW"


def _build_explanation(
    *,
    full_text: str,
    source: str,
    topic: str,
    engagement: Optional[int],
    risk: float,
    confidence: float,
) -> Dict[str, Any]:
    matched_misinfo_terms = _matched_terms(full_text, MISINFO_WORDING)[:4]
    matched_factcheck_terms = _matched_terms(full_text, FACTCHECK_HINTS)[:3]
    matched_manipulated_media_terms = _matched_terms(full_text, MANIPULATED_MEDIA_HINTS)[:3]
    matched_social_terms = _matched_terms(full_text, SOCIAL_MISINFO_HINTS)[:3]

    triggers: List[str] = []
    reasons: List[str] = []

    if matched_misinfo_terms:
        triggers.append("misinformation wording")
        reasons.append(
            "Detected misinformation-related wording: " + ", ".join(matched_misinfo_terms) + "."
        )

    if matched_factcheck_terms:
        triggers.append("fact-check context")
        reasons.append(
            "Detected fact-check/debunking language: " + ", ".join(matched_factcheck_terms) + "."
        )

    if matched_manipulated_media_terms:
        triggers.append("manipulated media")
        reasons.append(
            "Detected manipulated-media language: " + ", ".join(matched_manipulated_media_terms) + "."
        )

    if matched_social_terms:
        triggers.append("social circulation")
        reasons.append(
            "Detected social-spread wording: " + ", ".join(matched_social_terms) + "."
        )

    if topic != "other":
        triggers.append("topic relevance")
        reasons.append(f"Classified under monitored topic: {topic}.")

    if source == "Reddit" and engagement:
        if engagement >= 1000:
            triggers.append("high engagement")
            reasons.append(f"High engagement on social content (score {engagement}).")
        elif engagement >= 100:
            triggers.append("social activity")
            reasons.append(f"Moderate social engagement detected (score {engagement}).")

    if risk >= 0.65:
        reasons.append("Overall signal scored as high risk based on source type, wording, and spread indicators.")
    elif risk >= 0.35:
        reasons.append("Overall signal scored as medium risk based on wording and narrative relevance.")
    else:
        reasons.append("Overall signal scored as low risk but remains relevant for monitoring.")

    summary_parts: List[str] = []

    if matched_factcheck_terms:
        summary_parts.append("Contains fact-check or debunking wording")
    elif matched_manipulated_media_terms:
        summary_parts.append("Contains manipulated-media wording")
    elif matched_misinfo_terms:
        summary_parts.append("Contains misinformation/disinformation wording")
    else:
        summary_parts.append("Matches external monitoring criteria")

    if matched_social_terms:
        summary_parts.append("shows signs of online circulation")

    if topic != "other":
        summary_parts.append(f"in the {topic} topic")

    short_summary = " ".join(summary_parts).strip().rstrip(".") + "."

    return {
        "summary": short_summary,
        "reasons": reasons[:4],
        "triggers": triggers[:4],
        "matched_terms": {
            "misinformation": matched_misinfo_terms,
            "factcheck": matched_factcheck_terms,
            "manipulated_media": matched_manipulated_media_terms,
            "social": matched_social_terms,
        },
        "confidence_note": f"Confidence {round(confidence * 100)}% based on wording strength, source type, and signal pattern.",
    }


def _why_flagged(
    *,
    full_text: str,
    source: str,
    topic: str,
    engagement: Optional[int],
    risk: float,
    confidence: float,
) -> str:
    explanation = _build_explanation(
        full_text=full_text,
        source=source,
        topic=topic,
        engagement=engagement,
        risk=risk,
        confidence=confidence,
    )
    return explanation["summary"]


def _is_relevant(full_text: str, source: str, topic: str) -> bool:
    has_misinfo_words = _contains_misinfo_wording(full_text)
    has_social_hint = _contains_social_hint(full_text)
    topic_relevant = topic != "other"

    if _is_bad_false_positive(full_text):
        return False

    if source == "Reddit":
        return has_misinfo_words or (has_social_hint and topic_relevant)

    if source in {"BBC", "Reuters", "Google News"}:
        return has_misinfo_words

    return False


def _make_item(
    *,
    source: str,
    title: str,
    url: str,
    published: Optional[str],
    summary: str = "",
    item_type: str = "news",
    engagement: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    title = _clean_text(title)
    summary = _clean_text(summary)

    if not title or not url:
        return None

    full_text = f"{title}. {summary}".strip()
    topic = _infer_topic(full_text)

    if not _is_relevant(full_text, source, topic):
        return None

    risk = _risk_from_text(full_text, source, engagement)
    confidence = max(0.45, min(0.92, 0.45 + _wording_hits(full_text) * 0.07))
    explanation = _build_explanation(
        full_text=full_text,
        source=source,
        topic=topic,
        engagement=engagement,
        risk=risk,
        confidence=confidence,
    )

    return {
        "source": source,
        "publisher": source,
        "title": title,
        "claim": title,
        "summary": summary,
        "url": url,
        "published": published or "",
        "published_iso": _published_iso(published),
        "engagement": engagement,
        "risk": round(risk, 4),
        "confidence": round(confidence, 4),
        "topic": topic,
        "type": item_type,
        "verdict": "MONITOR",
        "signal_type": _signal_type(source, engagement, risk),
        "signal_strength": _signal_strength(risk),
        "source_credibility": _source_credibility(source),
        "why_flagged": explanation["summary"],
        "explanation": explanation,
    }


def fetch_google_news(limit: int = 12) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    feed = feedparser.parse(GOOGLE_NEWS_URL)

    for entry in feed.entries[: limit * 5]:
        row = _make_item(
            source="Google News",
            title=getattr(entry, "title", "") or "",
            url=getattr(entry, "link", "") or "",
            published=getattr(entry, "published", "") or "",
            summary=getattr(entry, "summary", "") or "",
            item_type="news",
        )
        if row:
            items.append(row)

    return items[:limit]


def fetch_bbc_news(limit: int = 12) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    feed = feedparser.parse(BBC_NEWS_URL)

    for entry in feed.entries[: limit * 5]:
        row = _make_item(
            source="BBC",
            title=getattr(entry, "title", "") or "",
            url=getattr(entry, "link", "") or "",
            published=getattr(entry, "published", "") or "",
            summary=getattr(entry, "summary", "") or "",
            item_type="news",
        )
        if row:
            items.append(row)

    return items[:limit]


def fetch_reuters_news(limit: int = 12) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    feed = feedparser.parse(REUTERS_NEWS_URL)

    for entry in feed.entries[: limit * 5]:
        row = _make_item(
            source="Reuters",
            title=getattr(entry, "title", "") or "",
            url=getattr(entry, "link", "") or "",
            published=getattr(entry, "published", "") or "",
            summary=getattr(entry, "summary", "") or "",
            item_type="news",
        )
        if row:
            items.append(row)

    return items[:limit]


def fetch_reddit(limit: int = 12) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []

    for reddit_url in REDDIT_URLS:
        try:
            data = _fetch_json(reddit_url)
        except Exception as e:
            print(f"live_feed reddit fetch error: {e}")
            continue

        for post in data.get("data", {}).get("children", [])[: limit * 5]:
            d = post.get("data", {})
            created = d.get("created_utc", 0)
            published = (
                datetime.fromtimestamp(float(created), tz=timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
                if created
                else ""
            )

            row = _make_item(
                source="Reddit",
                title=d.get("title") or "",
                url=f"https://reddit.com{d.get('permalink')}" if d.get("permalink") else "",
                published=published,
                summary=d.get("selftext") or "",
                item_type="social",
                engagement=int(d.get("score") or 0),
            )
            if row:
                items.append(row)

    items.sort(
        key=lambda x: (
            float(x.get("risk") or 0.0),
            float(x.get("engagement") or 0.0),
            float(x.get("confidence") or 0.0),
        ),
        reverse=True,
    )
    return items[:limit]


def _dedupe(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    out: List[Dict[str, Any]] = []

    for item in items:
        key = re.sub(r"\W+", " ", (item.get("title") or "").lower()).strip()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(item)

    return out


def get_live_feed(limit: int = 20) -> Dict[str, Any]:
    collected: List[Dict[str, Any]] = []
    debug_counts: Dict[str, int] = {}

    for name, fn in (
        ("Google News", fetch_google_news),
        ("BBC", fetch_bbc_news),
        ("Reuters", fetch_reuters_news),
        ("Reddit", fetch_reddit),
    ):
        try:
            rows = fn(limit=10)
            debug_counts[name] = len(rows)
            collected.extend(rows)
        except Exception as e:
            debug_counts[name] = 0
            print(f"live_feed error from {name}: {e}")

    collected = _dedupe(collected)
    collected.sort(
        key=lambda x: (
            float(x.get("risk") or 0.0),
            float(x.get("engagement") or 0.0),
            float(x.get("confidence") or 0.0),
        ),
        reverse=True,
    )

    if not collected:
        try:
            feed = feedparser.parse(GOOGLE_NEWS_URL)
            fallback_items: List[Dict[str, Any]] = []

            for entry in feed.entries[:limit]:
                title = _clean_text(getattr(entry, "title", "") or "")
                link = getattr(entry, "link", "") or ""
                published = getattr(entry, "published", "") or ""
                summary = _clean_text(getattr(entry, "summary", "") or "")

                if not title or not link:
                    continue

                fallback_items.append(
                    {
                        "source": "Google News",
                        "publisher": "Google News",
                        "title": title,
                        "claim": title,
                        "summary": summary,
                        "url": link,
                        "published": published,
                        "published_iso": _published_iso(published),
                        "engagement": None,
                        "risk": 0.40,
                        "confidence": 0.45,
                        "topic": _infer_topic(f"{title}. {summary}"),
                        "type": "news",
                        "verdict": "MONITOR",
                        "signal_type": "NEWS SIGNAL",
                        "signal_strength": "MEDIUM",
                        "source_credibility": 0.82,
                        "why_flagged": "Fallback external feed item.",
                        "explanation": {
                            "summary": "Fallback external feed item.",
                            "reasons": ["Primary filtered feeds returned no items, so a fallback feed item was shown."],
                            "triggers": ["fallback"],
                            "matched_terms": {
                                "misinformation": [],
                                "factcheck": [],
                                "manipulated_media": [],
                                "social": [],
                            },
                            "confidence_note": "Fallback confidence estimate.",
                        },
                    }
                )

            collected = fallback_items
        except Exception as e:
            print(f"live_feed fallback error: {e}")

    collected = collected[:limit]

    return {
        "generated_at": _now_iso(),
        "mode": "external_live_feed",
        "items": collected,
        "stats": {
            "active_claims": len(collected),
            "high_risk_alerts": sum(1 for x in collected if float(x.get("risk") or 0.0) >= 0.65),
            "total_mentions": sum(max(1, int(x.get("engagement") or 1)) for x in collected),
            "debug_counts": debug_counts,
        },
    }
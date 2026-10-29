"""Parallel evidence retrieval. Each source is optional and fails independently."""

from __future__ import annotations

import asyncio
import html
import logging
import re

from ..config import get_settings
from ..schemas import Evidence
from ..services import http
from ..services.sources import classify, domain_of

log = logging.getLogger(__name__)

_TAG = re.compile(r"<[^>]+>")
_STOP = set(
    """a an the and or but of to in on at for with by from as is are was were be been being it its this that these
those has have had do does did not no so if than then there their they them he she his her we our you your i me my
will would can could should may might must just very really about into over after before up down out more most
some any all every each also only even still such what which who whom whose when where why how""".split()
)


def _clean(s: str) -> str:
    return html.unescape(_TAG.sub("", s or "")).strip()


def keyword_query(claim: str, max_words: int = 12) -> str:
    words = re.findall(r"[\w'%.-]+", claim)
    kept = [w for w in words if w.lower() not in _STOP]
    return " ".join(kept[:max_words]) or claim[:120]


# ---------------------------------------------------------------- Google Fact Check


async def google_factcheck(claim: str) -> list[Evidence]:
    s = get_settings()
    if not s.google_factcheck_api_key:
        return []
    out: list[Evidence] = []
    for query in dict.fromkeys([claim[:200], keyword_query(claim, 8)]):  # exact first, then keywords
        data = await http.get_json(
            "https://factchecktools.googleapis.com/v1alpha1/claims:search",
            params={"query": query, "key": s.google_factcheck_api_key, "pageSize": 10},
        )
        for c in data.get("claims", []) or []:
            claim_text = c.get("text", "")
            for review in c.get("claimReview", []) or []:
                url = review.get("url", "")
                if not url:
                    continue
                pub = review.get("publisher") or {}
                _, cred = classify(url)
                out.append(
                    Evidence(
                        title=review.get("title") or f"Fact-check: {claim_text[:90]}",
                        url=url,
                        domain=domain_of(url),
                        snippet=claim_text,
                        kind="factcheck",
                        publisher=pub.get("name") or pub.get("site") or "",
                        rating=review.get("textualRating"),
                        credibility=max(cred, 0.85),
                        published=(review.get("reviewDate") or c.get("claimDate") or "")[:10] or None,
                    )
                )
        if len(out) >= 3:
            break
    return out


# ---------------------------------------------------------------- Wikipedia


async def wikipedia(claim: str) -> list[Evidence]:
    if not get_settings().enable_wikipedia:
        return []
    data = await http.get_json(
        "https://en.wikipedia.org/w/api.php",
        params={
            "action": "query",
            "list": "search",
            "srsearch": keyword_query(claim, 8),
            "format": "json",
            "srlimit": 3,
            "srprop": "snippet|timestamp",
        },
    )
    hits = (data.get("query") or {}).get("search") or []
    if not hits:
        return []
    # Fetch lead extracts for richer context than the search snippet.
    titles = "|".join(h["title"] for h in hits)
    ex = await http.get_json(
        "https://en.wikipedia.org/w/api.php",
        params={
            "action": "query",
            "prop": "extracts",
            "exintro": 1,
            "explaintext": 1,
            "exsentences": 5,
            "titles": titles,
            "format": "json",
            "redirects": 1,
        },
    )
    extracts = {p.get("title"): p.get("extract", "") for p in ((ex.get("query") or {}).get("pages") or {}).values()}
    out = []
    for h in hits:
        title = h["title"]
        url = f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"
        out.append(
            Evidence(
                title=f"{title} — Wikipedia",
                url=url,
                domain="en.wikipedia.org",
                snippet=(extracts.get(title) or _clean(h.get("snippet", "")))[:900],
                kind="encyclopedia",
                publisher="Wikipedia",
                credibility=0.75,
                published=(h.get("timestamp") or "")[:10] or None,
            )
        )
    return out


# ---------------------------------------------------------------- Web search APIs


async def brave(claim: str) -> list[Evidence]:
    s = get_settings()
    if not s.brave_api_key:
        return []
    data = await http.get_json(
        "https://api.search.brave.com/res/v1/web/search",
        params={"q": claim[:300], "count": 8, "safesearch": "moderate"},
        headers={"X-Subscription-Token": s.brave_api_key, "Accept": "application/json"},
    )
    out = []
    for r in ((data.get("web") or {}).get("results") or [])[:8]:
        url = r.get("url", "")
        kind, cred = classify(url)
        out.append(
            Evidence(
                title=_clean(r.get("title", "")),
                url=url,
                domain=domain_of(url),
                snippet=_clean(r.get("description", "")),
                kind=kind,
                credibility=cred,
                published=r.get("page_age") or r.get("age"),
            )
        )
    return out


async def tavily(claim: str) -> list[Evidence]:
    s = get_settings()
    if not s.tavily_api_key:
        return []
    data = await http.post_json(
        "https://api.tavily.com/search",
        payload={"query": claim[:380], "max_results": 8, "search_depth": "basic", "include_answer": False},
        headers={"Authorization": f"Bearer {s.tavily_api_key}"},
    )
    out = []
    for r in (data.get("results") or [])[:8]:
        url = r.get("url", "")
        kind, cred = classify(url)
        out.append(
            Evidence(
                title=r.get("title", ""),
                url=url,
                domain=domain_of(url),
                snippet=(r.get("content") or "")[:900],
                kind=kind,
                credibility=cred,
                published=r.get("published_date"),
            )
        )
    return out


SOURCES = {
    "google_factcheck": google_factcheck,
    "wikipedia": wikipedia,
    "brave": brave,
    "tavily": tavily,
}


def active_sources() -> dict[str, bool]:
    s = get_settings()
    return {
        "google_factcheck": bool(s.google_factcheck_api_key),
        "wikipedia": s.enable_wikipedia,
        "brave": bool(s.brave_api_key),
        "tavily": bool(s.tavily_api_key),
    }


async def gather_evidence(claim: str, max_items: int = 12) -> tuple[list[Evidence], list[str], list[str]]:
    """Return (evidence, sources_that_returned_results, warnings)."""
    enabled = [n for n, on in active_sources().items() if on]
    results = await asyncio.gather(*(SOURCES[n](claim) for n in enabled), return_exceptions=True)

    evidence: list[Evidence] = []
    used, warnings = [], []
    for name, res in zip(enabled, results, strict=True):
        if isinstance(res, BaseException):
            log.warning("source %s failed: %r", name, res)
            warnings.append(f"{name} unavailable ({type(res).__name__})")
            continue
        if res:
            used.append(name)
            evidence.extend(res)

    seen, unique = set(), []
    for e in evidence:
        key = e.url.split("#")[0].rstrip("/")
        if key and key not in seen:
            seen.add(key)
            unique.append(e)
    # Fact-checks first, then by credibility.
    unique.sort(key=lambda e: (e.kind != "factcheck", -e.credibility))
    return unique[:max_items], used, warnings

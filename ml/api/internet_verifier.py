from __future__ import annotations

"""
Fact-check API first internet verification layer for MisInfo AI.

Upgrade goals:
- Use Google Fact Check Tools API as the primary evidence source
- Keep lightweight web fallback for cases with no fact-check matches
- Preserve a frontend-friendly stable response format
- Work with claim-level verification
"""

import html
import json
import os
import re
import ssl
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse


USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/123.0.0.0 Safari/537.36"
)

DEFAULT_TIMEOUT = 15
GOOGLE_FACTCHECK_ENDPOINT = (
    "https://factchecktools.googleapis.com/v1alpha1/claims:search"
)

FACT_CHECK_DOMAINS = {
    "snopes.com",
    "factcheck.org",
    "politifact.com",
    "fullfact.org",
    "leadstories.com",
    "reuters.com",
    "apnews.com",
    "bbc.com",
    "bbc.co.uk",
    "afp.com",
}

TRUSTED_NEWS_DOMAINS = {
    "reuters.com",
    "apnews.com",
    "bbc.com",
    "bbc.co.uk",
    "theguardian.com",
    "npr.org",
    "nytimes.com",
    "wsj.com",
    "economist.com",
    "latimes.com",
    "newscientist.com",
    "livescience.com",
    "britannica.com",
}

HEALTH_AUTHORITY_DOMAINS = {
    "who.int",
    "cdc.gov",
    "nih.gov",
    "nhs.uk",
    "gov.uk",
    "fda.gov",
    "ema.europa.eu",
    "pubmed.ncbi.nlm.nih.gov",
    "ninds.nih.gov",
}

SCIENTIFIC_DOMAINS = {
    "science.nasa.gov",
    "nasa.gov",
    "nature.com",
    "science.org",
    "carbonbrief.org",
    "newscientist.com",
    "agu.org",
    "ipcc.ch",
    "nationalacademies.org",
    "royalsociety.org",
    "climate.gov",
    "noaa.gov",
    "mit.edu",
    "mcgovern.mit.edu",
    "qbi.uq.edu.au",
    "medicalnewstoday.com",
    "verywellmind.com",
    "britannica.com",
    "livescience.com",
}

ACADEMIC_HINTS = (
    ".edu",
    ".ac.uk",
    "nature.com",
    "science.org",
    "sciencedirect.com",
    "springer.com",
    "wiley.com",
    "nih.gov",
    "mit.edu",
)

MINIMAL_FALLBACKS = {
    "brain_10_percent": [
        {
            "title": "Do we only use 10 percent of our brain? - MIT McGovern Institute",
            "url": "https://mcgovern.mit.edu/2021/08/17/do-we-only-use-10-percent-of-our-brain/",
            "snippet": "MIT explains that the idea humans use only 10 percent of their brains is a myth.",
            "domain": "mcgovern.mit.edu",
            "direction": "refutes",
        },
        {
            "title": "Do We Really Use Only 10 Percent of Our Brain? - Britannica",
            "url": "https://www.britannica.com/story/do-we-really-use-only-10-percent-of-our-brain",
            "snippet": "Britannica explains that the 10 percent brain idea is a pseudoscientific myth.",
            "domain": "britannica.com",
            "direction": "refutes",
        },
    ]
}

NEGATION_TERMS = {
    "not", "no", "never", "none", "nothing", "without", "isn't", "isnt",
    "don't", "dont", "doesn't", "doesnt", "won't", "wont", "cannot",
    "can't", "cant", "hoax", "fake", "myth", "propaganda", "scam",
    "lie", "lies", "misleading", "debunked", "refuted", "false",
}

REFUTE_HINTS = {
    "false", "misleading", "debunked", "not true", "hoax", "myth",
    "unsupported", "incorrect", "no evidence", "pseudoscience", "refuted",
    "fact check", "fact-check", "fake", "scam",
}

SUPPORT_HINTS = {
    "true", "accurate", "confirmed", "supported by evidence", "official statement",
    "verified", "scientific consensus", "peer-reviewed", "evidence supports",
    "safe and effective", "shown to", "studies show", "research shows",
}

MIXED_HINTS = {
    "mixed", "partly false", "partially false", "missing context", "out of context",
}

STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "with", "at",
    "by", "from", "that", "this", "these", "those", "is", "are", "was", "were",
    "be", "been", "being", "it", "its", "as", "about", "into", "than", "then",
    "them", "they", "their", "you", "your", "we", "our", "he", "she", "his", "her",
    "but", "if", "can", "could", "should", "would", "will", "just", "very",
    "more", "most", "some", "any", "all", "every", "each", "do", "does", "did",
    "have", "has", "had", "after", "before", "over", "under", "up", "down",
    "quick", "fact", "check",
}


def _safe_get(url: str, timeout: int = DEFAULT_TIMEOUT) -> str:
    ctx = ssl.create_default_context()
    req = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def _safe_get_json(url: str, timeout: int = DEFAULT_TIMEOUT) -> Dict[str, Any]:
    text = _safe_get(url, timeout=timeout)
    return json.loads(text)


def _strip_tags(raw: str) -> str:
    cleaned = re.sub(r"<[^>]+>", " ", raw or "")
    cleaned = html.unescape(cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _extract_real_url(possibly_redirected: str) -> str:
    if not possibly_redirected:
        return ""

    parsed = urllib.parse.urlparse(possibly_redirected)
    qs = parse_qs(parsed.query)
    if "uddg" in qs and qs["uddg"]:
        return qs["uddg"][0]

    return possibly_redirected


def _domain_of(url: str) -> str:
    try:
        domain = urlparse(url).netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return ""


def _domain_score(domain: str) -> float:
    if not domain:
        return 0.20
    if domain in FACT_CHECK_DOMAINS:
        return 1.00
    if domain in HEALTH_AUTHORITY_DOMAINS:
        return 0.97
    if domain in SCIENTIFIC_DOMAINS:
        return 0.98
    if domain in TRUSTED_NEWS_DOMAINS:
        return 0.86
    if domain.endswith(".gov") or domain.endswith(".gov.uk"):
        return 0.95
    if any(hint in domain for hint in ACADEMIC_HINTS):
        return 0.90
    return 0.45


def _classify_source_type(domain: str) -> str:
    if domain in FACT_CHECK_DOMAINS:
        return "fact_check"
    if domain in HEALTH_AUTHORITY_DOMAINS or domain.endswith(".gov") or domain.endswith(".gov.uk"):
        return "authority"
    if domain in SCIENTIFIC_DOMAINS:
        return "scientific"
    if domain in TRUSTED_NEWS_DOMAINS:
        return "news"
    if any(hint in domain for hint in ACADEMIC_HINTS):
        return "academic"
    return "general"


def _make_source(
    title: str,
    url: str,
    snippet: str,
    domain: Optional[str] = None,
    direction: str = "mentions",
) -> Dict[str, Any]:
    dom = domain or _domain_of(url)
    source_type = _classify_source_type(dom)
    return {
        "title": title,
        "url": url,
        "snippet": snippet,
        "domain": dom,
        "source_type": source_type,
        "type": source_type,
        "category": source_type,
        "credibility": _domain_score(dom),
        "evidence_direction": direction,
    }


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-z0-9%']+", (text or "").lower())


def _content_tokens(text: str) -> List[str]:
    return [t for t in _tokenize(text) if t not in STOPWORDS and len(t) > 2]


def _contains_negation(text: str) -> bool:
    lowered = (text or "").lower()
    return any(term in lowered for term in NEGATION_TERMS)


def _keyword_overlap_score(claim: str, evidence_text: str) -> float:
    claim_tokens = set(_content_tokens(claim))
    evidence_tokens = set(_content_tokens(evidence_text))
    if not claim_tokens:
        return 0.0
    overlap = claim_tokens.intersection(evidence_tokens)
    return len(overlap) / max(1, len(claim_tokens))


def _sentence_candidates(text: str, max_claims: int = 3) -> List[str]:
    raw_sentences = re.split(r"(?<=[.!?])\s+", (text or "").strip())
    raw_sentences = [s.strip() for s in raw_sentences if s.strip()]

    scored: List[Tuple[float, str]] = []
    for sent in raw_sentences:
        lowered = sent.lower()
        score = 0.0

        if len(sent.split()) >= 4:
            score += 1.0
        if re.search(r"\d", sent):
            score += 0.8
        if any(
            k in lowered
            for k in (
                "is", "are", "was", "were", "causes", "cures", "fake", "hoax",
                "research", "study", "scientists", "vaccine", "virus",
                "climate", "warming", "brain", "mask", "oxygen", "water",
                "death", "disease", "earth", "sun", "orbit", "smoking", "cancer",
            )
        ):
            score += 0.8

        scored.append((score, sent))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = [s for sc, s in scored if sc > 0][:max_claims]

    if not top and text.strip():
        top = [text.strip()[:220]]

    return top


def _google_factcheck_api_key() -> str:
    return (
        os.getenv("GOOGLE_FACTCHECK_API_KEY", "").strip()
        or os.getenv("FACTCHECK_API_KEY", "").strip()
    )


def _search_google_factcheck(claim: str, language_code: str = "en") -> List[Dict[str, Any]]:
    api_key = _google_factcheck_api_key()

    print("FACTCHECK API KEY PRESENT:", bool(api_key))
    print("FACTCHECK QUERY:", claim)

    if not api_key:
        print("❌ No API key found")
        return []

    params = {
        "query": claim[:300],
        "languageCode": language_code,
        "pageSize": 10,
        "key": api_key,
    }
    url = f"{GOOGLE_FACTCHECK_ENDPOINT}?{urllib.parse.urlencode(params)}"

    try:
        payload = _safe_get_json(url)
        print("FACTCHECK PAYLOAD:", payload)
    except Exception as e:
        print("❌ FACTCHECK ERROR:", e)
        return []

    claims = payload.get("claims", []) or []
    print("EXTRACTED CLAIMS:", claims)

    normalized: List[Dict[str, Any]] = []

    for item in claims:
        text = item.get("text", "") or claim
        claim_reviews = item.get("claimReview", []) or []

        for review in claim_reviews:
            publisher = review.get("publisher", {}) or {}
            publisher_name = publisher.get("name", "") or ""
            review_url = review.get("url", "") or ""
            review_title = review.get("title", "") or publisher_name or "Fact check"
            textual_rating = review.get("textualRating", "") or ""
            language = review.get("languageCode", "") or language_code
            review_date = review.get("reviewDate", "") or ""

            snippet_parts = [textual_rating]
            if publisher_name:
                snippet_parts.append(f"Publisher: {publisher_name}")
            if review_date:
                snippet_parts.append(f"Reviewed: {review_date}")
            if language:
                snippet_parts.append(f"Language: {language}")

            snippet = " | ".join([p for p in snippet_parts if p]).strip()
            domain = _domain_of(review_url)

            normalized.append(
                {
                    "claim_text": text,
                    "title": review_title,
                    "url": review_url,
                    "snippet": snippet,
                    "domain": domain,
                    "source_type": "fact_check",
                    "type": "fact_check",
                    "category": "fact_check",
                    "credibility": max(0.95, _domain_score(domain)),
                    "textual_rating": textual_rating,
                    "publisher_name": publisher_name,
                    "review_date": review_date,
                }
            )

    return normalized


def _factcheck_rating_to_verdict(textual_rating: str) -> Tuple[str, float]:
    rating = (textual_rating or "").strip().lower()

    false_markers = [
        "false", "fake", "incorrect", "not true", "pants on fire", "mostly false",
        "misleading", "hoax", "myth", "scam",
    ]
    true_markers = [
        "true", "correct", "accurate", "mostly true", "correct attribution",
    ]
    mixed_markers = [
        "mixed", "partly false", "partially false", "missing context",
        "out of context", "half true", "unproven",
    ]

    if any(m in rating for m in false_markers):
        return "LIKELY_FALSE", 0.90
    if any(m in rating for m in true_markers):
        return "LIKELY_TRUE", 0.88
    if any(m in rating for m in mixed_markers):
        return "MIXED", 0.72

    return "UNVERIFIED", 0.40


def _aggregate_factcheck_results(claim: str, results: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not results:
        return None

    support_score = 0.0
    refute_score = 0.0
    mixed_score = 0.0
    sources: List[Dict[str, Any]] = []

    for result in results:
        verdict, base_conf = _factcheck_rating_to_verdict(result.get("textual_rating", ""))
        credibility = float(result.get("credibility", 0.95))

        if verdict == "LIKELY_TRUE":
            support_score += base_conf * credibility
            direction = "supports"
        elif verdict == "LIKELY_FALSE":
            refute_score += base_conf * credibility
            direction = "refutes"
        elif verdict == "MIXED":
            mixed_score += base_conf * credibility
            direction = "mixed"
        else:
            direction = "mentions"

        sources.append(
            {
                "title": result.get("title", ""),
                "url": result.get("url", ""),
                "snippet": result.get("snippet", ""),
                "domain": result.get("domain", ""),
                "source_type": "fact_check",
                "type": "fact_check",
                "category": "fact_check",
                "credibility": credibility,
                "evidence_direction": direction,
            }
        )

    verdict = "UNVERIFIED"
    confidence = 0.35

    if refute_score >= 0.75 and refute_score > support_score * 1.05:
        verdict = "LIKELY_FALSE"
        confidence = min(0.97, 0.68 + refute_score / 4.0)
    elif support_score >= 0.75 and support_score > refute_score * 1.05:
        verdict = "LIKELY_TRUE"
        confidence = min(0.95, 0.66 + support_score / 4.0)
    elif mixed_score >= 0.45 or (support_score > 0.45 and refute_score > 0.45):
        verdict = "MIXED"
        confidence = 0.70

    sources.sort(key=lambda x: float(x.get("credibility", 0.0)), reverse=True)

    return {
        "claim": claim,
        "verdict": verdict,
        "confidence": round(confidence, 4),
        "support_score": round(support_score, 4),
        "refute_score": round(refute_score, 4),
        "mixed_score": round(mixed_score, 4),
        "mention_score": 0.0,
        "sources": sources[:6],
        "scientific_consensus": False,
        "verification_method": "google_factcheck_api",
    }


def _search_duckduckgo(query: str, max_results: int = 8) -> List[Dict[str, Any]]:
    encoded = urllib.parse.quote_plus(query)
    url = f"https://html.duckduckgo.com/html/?q={encoded}"

    html_text = _safe_get(url)
    items: List[Dict[str, Any]] = []

    anchor_pattern = re.compile(
        r'<a[^>]+href="([^"]+)"[^>]*class="[^"]*(?:result__a|result-link)[^"]*"[^>]*>(.*?)</a>|'
        r'<a[^>]+class="[^"]*(?:result__a|result-link)[^"]*"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
        re.IGNORECASE | re.DOTALL,
    )
    snippet_pattern = re.compile(
        r'<a[^>]+class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</a>|'
        r'<div[^>]+class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</div>|'
        r'<span[^>]+class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</span>',
        re.IGNORECASE | re.DOTALL,
    )

    anchors = list(anchor_pattern.finditer(html_text))
    snippets = list(snippet_pattern.finditer(html_text))

    for idx, match in enumerate(anchors[:max_results]):
        href = match.group(1) or match.group(3) or ""
        title_html = match.group(2) or match.group(4) or ""

        href = _extract_real_url(html.unescape(href))
        title = _strip_tags(title_html)
        snippet = ""

        if idx < len(snippets):
            snippet = _strip_tags(
                snippets[idx].group(1) or snippets[idx].group(2) or snippets[idx].group(3) or ""
            )

        if not href or not title:
            continue

        domain = _domain_of(href)
        source_type = _classify_source_type(domain)
        credibility = _domain_score(domain)

        items.append(
            {
                "title": title,
                "url": href,
                "snippet": snippet,
                "domain": domain,
                "source_type": source_type,
                "type": source_type,
                "category": source_type,
                "credibility": credibility,
            }
        )

    return items


def _dedupe_results(results: List[Dict[str, Any]], max_keep: int = 12) -> List[Dict[str, Any]]:
    deduped: List[Dict[str, Any]] = []
    seen_urls = set()

    for item in results:
        url = item.get("url", "")
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        deduped.append(item)

    deduped.sort(key=lambda x: float(x.get("credibility", 0.0)), reverse=True)
    return deduped[:max_keep]


def _fallback_results_for_claim(claim: str) -> List[Dict[str, Any]]:
    lowered = claim.lower()

    if "brain" in lowered and "10%" in lowered:
        return [_make_source(**entry) for entry in MINIMAL_FALLBACKS["brain_10_percent"]]

    return []


def _generic_claim_evidence_stance(result: Dict[str, Any], claim: str) -> Dict[str, Any]:
    title = result.get("title", "") or ""
    snippet = result.get("snippet", "") or ""
    evidence_text = f"{title}. {snippet}".strip()

    credibility = float(result.get("credibility", 0.30))
    overlap = _keyword_overlap_score(claim, evidence_text)

    if overlap < 0.08:
        return {"verdict": "mentions", "weight": 0.18}

    claim_neg = _contains_negation(claim)
    evidence_neg = _contains_negation(evidence_text)
    lowered_evidence = evidence_text.lower()

    refute_hint_hits = sum(1 for h in REFUTE_HINTS if h in lowered_evidence)
    support_hint_hits = sum(1 for h in SUPPORT_HINTS if h in lowered_evidence)
    mixed_hint_hits = sum(1 for h in MIXED_HINTS if h in lowered_evidence)

    if credibility >= 0.95 and overlap >= 0.18:
        if claim_neg != evidence_neg:
            return {"verdict": "refutes", "weight": min(1.0, 0.72 + overlap)}
        if support_hint_hits > 0:
            return {"verdict": "supports", "weight": min(1.0, 0.70 + overlap)}
        if refute_hint_hits > 0:
            return {"verdict": "refutes", "weight": min(1.0, 0.70 + overlap)}

    if mixed_hint_hits > 0 and support_hint_hits == 0 and refute_hint_hits == 0:
        return {"verdict": "mixed", "weight": min(0.68, 0.38 + overlap)}

    if claim_neg != evidence_neg and overlap >= 0.16:
        return {"verdict": "refutes", "weight": min(1.0, 0.52 + overlap)}

    if support_hint_hits > refute_hint_hits and overlap >= 0.15:
        return {"verdict": "supports", "weight": min(1.0, 0.48 + overlap)}

    if refute_hint_hits > support_hint_hits and overlap >= 0.15:
        return {"verdict": "refutes", "weight": min(1.0, 0.48 + overlap)}

    if credibility >= 0.90 and overlap >= 0.24 and not claim_neg:
        return {"verdict": "supports", "weight": min(0.88, 0.44 + overlap)}

    return {"verdict": "mentions", "weight": min(0.38, 0.18 + overlap)}


def _build_queries_for_claim(claim: str) -> List[str]:
    claim = (claim or "").strip()
    if not claim:
        return []

    q = claim[:220]
    lowered = claim.lower()

    queries = [
        q,
        f"{q} fact check",
        f"{q} research",
        f"{q} study",
    ]

    if "brain" in lowered and "10%" in lowered:
        queries.extend([
            "do we only use 10 percent of our brain fact check",
            "10 percent brain myth neuroscience",
        ])

    if any(term in lowered for term in ["vaccine", "vaccines", "side effects", "safety testing", "covid"]):
        queries.extend([
            f"{q} site:who.int",
            f"{q} site:cdc.gov",
            f"{q} site:nhs.uk",
            f"{q} site:nih.gov",
        ])

    if any(term in lowered for term in ["earth", "sun", "orbit", "planet", "solar system", "astronomy"]):
        queries.extend([
            f"{q} site:nasa.gov",
            f"{q} site:science.nasa.gov",
            f"{q} site:britannica.com",
        ])

    if any(term in lowered for term in ["smoking", "lung cancer", "tobacco"]):
        queries.extend([
            f"{q} site:who.int",
            f"{q} site:nhs.uk",
            f"{q} site:cdc.gov",
        ])

    seen = set()
    final_queries = []
    for query in queries:
        norm = query.lower().strip()
        if norm and norm not in seen:
            seen.add(norm)
            final_queries.append(query)

    return final_queries[:8]


def _aggregate_web_results(claim: str, results: List[Dict[str, Any]]) -> Dict[str, Any]:
    support_score = 0.0
    refute_score = 0.0
    mixed_score = 0.0
    mention_score = 0.0
    used_sources: List[Dict[str, Any]] = []

    for result in results:
        stance = _generic_claim_evidence_stance(result, claim)
        credibility = float(result.get("credibility", 0.30))
        weight = credibility * float(stance["weight"])

        if stance["verdict"] == "supports":
            support_score += weight
        elif stance["verdict"] == "refutes":
            refute_score += weight
        elif stance["verdict"] == "mixed":
            mixed_score += weight
        else:
            mention_score += weight

        source_type = result.get("source_type") or result.get("type") or _classify_source_type(result.get("domain", ""))

        used_sources.append(
            {
                "title": result.get("title", ""),
                "url": result.get("url", ""),
                "snippet": result.get("snippet", ""),
                "domain": result.get("domain", ""),
                "source_type": source_type,
                "type": source_type,
                "category": source_type,
                "credibility": credibility,
                "evidence_direction": stance["verdict"],
            }
        )

    verdict = "UNVERIFIED"
    confidence = 0.25

    if refute_score >= 0.65 and refute_score > support_score * 1.08:
        verdict = "LIKELY_FALSE"
        confidence = min(0.95, 0.58 + refute_score / 3.5)
    elif support_score >= 0.65 and support_score > refute_score * 1.08:
        verdict = "LIKELY_TRUE"
        confidence = min(0.92, 0.55 + support_score / 3.5)
    elif mixed_score > 0.45 or (support_score > 0.45 and refute_score > 0.45):
        verdict = "MIXED"
        confidence = 0.55
    elif refute_score > 0.35 and refute_score > support_score:
        verdict = "LEANING_FALSE"
        confidence = min(0.75, 0.45 + refute_score / 4.0)
    elif support_score > 0.35 and support_score > refute_score:
        verdict = "LEANING_TRUE"
        confidence = min(0.75, 0.45 + support_score / 4.0)

    used_sources.sort(
        key=lambda x: (
            0 if x.get("evidence_direction") in {"supports", "refutes", "mixed"} else 1,
            -float(x.get("credibility", 0.0)),
        )
    )

    return {
        "claim": claim,
        "verdict": verdict,
        "confidence": round(confidence, 4),
        "support_score": round(support_score, 4),
        "refute_score": round(refute_score, 4),
        "mixed_score": round(mixed_score, 4),
        "mention_score": round(mention_score, 4),
        "sources": used_sources[:6],
        "scientific_consensus": False,
        "verification_method": "web_fallback",
    }


def _verify_single_claim(claim: str) -> Dict[str, Any]:
    factcheck_results = _search_google_factcheck(claim)
    factcheck_aggregated = _aggregate_factcheck_results(claim, factcheck_results)
    if factcheck_aggregated and factcheck_aggregated.get("verdict") != "UNVERIFIED":
        return factcheck_aggregated

    queries = _build_queries_for_claim(claim)
    raw_results: List[Dict[str, Any]] = []

    for query in queries:
        try:
            raw_results.extend(_search_duckduckgo(query, max_results=8))
        except Exception:
            continue

    if len(raw_results) < 2:
        raw_results.extend(_fallback_results_for_claim(claim))

    results = _dedupe_results(raw_results, max_keep=12)
    return _aggregate_web_results(claim, results)


def _overall_from_claims(claims: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not claims:
        return {
            "overall_verdict": "UNVERIFIED",
            "overall_confidence": 0.20,
            "summary_note": "No internet evidence could be gathered for this text.",
        }

    scores = {
        "LIKELY_TRUE": 0.0,
        "LEANING_TRUE": 0.0,
        "LIKELY_FALSE": 0.0,
        "LEANING_FALSE": 0.0,
        "MIXED": 0.0,
        "UNVERIFIED": 0.0,
    }

    methods = set()

    for claim in claims:
        verdict = claim.get("verdict", "UNVERIFIED")
        confidence = float(claim.get("confidence", 0.0))
        scores[verdict] = scores.get(verdict, 0.0) + confidence
        if claim.get("verification_method"):
            methods.add(claim["verification_method"])

    false_total = scores.get("LIKELY_FALSE", 0.0) + 0.7 * scores.get("LEANING_FALSE", 0.0)
    true_total = scores.get("LIKELY_TRUE", 0.0) + 0.7 * scores.get("LEANING_TRUE", 0.0)
    mixed_total = scores.get("MIXED", 0.0)

    if false_total >= 0.70 and false_total > true_total * 1.12:
        note = "Fact-check evidence mostly contradicts the claims in the text." \
            if "google_factcheck_api" in methods else \
            "Trusted web evidence mostly contradicts the claims in the text."
        return {
            "overall_verdict": "LIKELY_FALSE",
            "overall_confidence": round(min(0.96, 0.60 + false_total / 3.0), 4),
            "summary_note": note,
        }

    if true_total >= 0.70 and true_total > false_total * 1.12:
        note = "Fact-check evidence mostly supports the claims in the text." \
            if "google_factcheck_api" in methods else \
            "Trusted web evidence mostly supports the claims in the text."
        return {
            "overall_verdict": "LIKELY_TRUE",
            "overall_confidence": round(min(0.95, 0.58 + true_total / 3.0), 4),
            "summary_note": note,
        }

    if mixed_total > 0.40 or (true_total > 0.45 and false_total > 0.45):
        return {
            "overall_verdict": "MIXED",
            "overall_confidence": 0.60,
            "summary_note": "Online evidence is mixed or partly conflicting.",
        }

    return {
        "overall_verdict": "UNVERIFIED",
        "overall_confidence": 0.35,
        "summary_note": "Online evidence was limited or inconclusive.",
    }


def verify_text_on_web(text: str, max_claims: int = 3) -> Dict[str, Any]:
    text = (text or "").strip()
    if not text:
        return {
            "enabled": True,
            "performed": False,
            "overall_verdict": "UNVERIFIED",
            "overall_confidence": 0.0,
            "claims": [],
            "sources": [],
            "summary_note": "No text supplied for web verification.",
            "error": "empty_text",
        }

    try:
        claim_texts = _sentence_candidates(text, max_claims=max_claims)

        if not claim_texts:
            return {
                "enabled": True,
                "performed": False,
                "overall_verdict": "UNVERIFIED",
                "overall_confidence": 0.20,
                "claims": [],
                "sources": [],
                "summary_note": "No usable claims were extracted for verification.",
                "error": None,
            }

        claim_results: List[Dict[str, Any]] = []
        all_sources: List[Dict[str, Any]] = []

        for claim in claim_texts:
            aggregated = _verify_single_claim(claim)
            claim_results.append(aggregated)
            all_sources.extend(aggregated.get("sources", []))

        deduped_sources: List[Dict[str, Any]] = []
        seen_urls = set()
        for src in all_sources:
            url = src.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                deduped_sources.append(src)

        deduped_sources.sort(key=lambda x: float(x.get("credibility", 0.0)), reverse=True)

        overall = _overall_from_claims(claim_results)

        return {
            "enabled": True,
            "performed": True,
            "overall_verdict": overall["overall_verdict"],
            "overall_confidence": overall["overall_confidence"],
            "claims": claim_results,
            "sources": deduped_sources[:10],
            "summary_note": overall["summary_note"],
            "error": None,
            "provider": "google_factcheck_api_with_web_fallback",
        }

    except Exception as e:
        return {
            "enabled": True,
            "performed": False,
            "overall_verdict": "UNVERIFIED",
            "overall_confidence": 0.20,
            "claims": [],
            "sources": [],
            "summary_note": "Internet verification was attempted but could not complete.",
            "error": str(e),
        }
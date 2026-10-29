"""Runs the full analysis and streams progress events.

Events (all dicts with "event" and "data"):
  input         {"text": str, "input_type": str, "source_url": str|None}
  stage         {"stage": str, "status": "running"|"done"|"skipped", "detail": str}
  claims        {"claims": [Claim]}
  tactics       {"tactics": [Tactic], "score": float}
  style         StyleSignal
  claim_result  ClaimResult
  result        AnalysisResult
  error         {"message": str}
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from rapidfuzz import fuzz

from ..config import get_settings
from ..llm import get_provider
from ..llm.heuristic_provider import HeuristicProvider, heuristic_claims
from ..schemas import AnalysisResult, Claim, ClaimResult, Evidence, PipelineInfo, Span
from ..services.sources import is_satire
from .aggregate import GUIDANCE, HEADLINES, aggregate, default_summary
from .retrieval import gather_evidence
from .style import style_signal
from .tactics import detect_tactics

log = logging.getLogger(__name__)


def _ev(event: str, data: Any) -> dict:
    if hasattr(data, "model_dump"):
        data = data.model_dump(mode="json")
    return {"event": event, "data": data}


def locate_span(text: str, quote: str, claim: str) -> Span | None:
    """Find where a claim came from in the original text, for highlighting."""
    for needle in (quote, claim):
        needle = (needle or "").strip()
        if len(needle) < 6:
            continue
        i = text.lower().find(needle.lower())
        if i >= 0:
            return Span(start=i, end=i + len(needle), text=text[i : i + len(needle)])
    # Fuzzy: best matching sentence-sized window
    target = quote or claim
    best, best_score = None, 0.0
    for start in range(0, max(1, len(text) - 20), 20):
        window = text[start : start + len(target) + 40]
        score = fuzz.partial_ratio(target.lower(), window.lower())
        if score > best_score:
            best, best_score = (start, start + len(window)), score
    if best and best_score >= 80:
        return Span(start=best[0], end=min(len(text), best[1]), text=text[best[0] : best[1]])
    return None


async def _check_claim(claim: Claim, context: str, use_web: bool, warnings: list[str], sources_used: set[str]) -> ClaimResult:
    provider = get_provider()
    evidence: list[Evidence] = []
    if use_web:
        evidence, used, warns = await gather_evidence(claim.text)
        sources_used.update(used)
        warnings.extend(w for w in warns if w not in warnings)

    method = "llm" if not isinstance(provider, HeuristicProvider) else "factcheck_match"
    try:
        outcome = await provider.verify_claim(claim.text, evidence, context, allow_search=use_web)
    except Exception as e:  # noqa: BLE001
        log.exception("LLM verification failed")
        msg = f"AI verification failed for a claim ({type(e).__name__}); used fact-check matching instead."
        if msg not in warnings:
            warnings.append(msg)
        outcome = await HeuristicProvider().verify_claim(claim.text, evidence, context, use_web)
        method = "factcheck_match"

    for idx, stance in outcome.stances.items():
        if 0 <= idx < len(evidence):
            evidence[idx].stance = stance  # type: ignore[assignment]
    if outcome.extra_evidence:
        sources_used.add("claude_web_search")
        known = {e.url for e in evidence}
        evidence.extend(e for e in outcome.extra_evidence if e.url not in known)

    if outcome.verdict == "UNVERIFIABLE" and method == "factcheck_match":
        method = "heuristic"
    # Relevant evidence first: judged stances, then credibility.
    evidence.sort(key=lambda e: (e.stance == "neutral", -e.credibility))
    return ClaimResult(
        claim=claim,
        verdict=outcome.verdict,
        confidence=round(outcome.confidence, 3),
        reasoning=outcome.reasoning,
        evidence=evidence[:10],
        method=method,  # type: ignore[arg-type]
    )


async def run_analysis(
    text: str,
    *,
    use_web: bool = True,
    input_type: str = "text",
    source_url: str | None = None,
    extracted_text: str | None = None,
) -> AsyncIterator[dict]:
    s = get_settings()
    provider = get_provider()
    started = time.perf_counter()
    deadline = started + s.pipeline_budget_s
    timings: dict[str, float] = {}
    warnings: list[str] = []
    sources_used: set[str] = set()
    text = text.strip()[: s.max_input_chars]

    def mark(name: str, t0: float) -> None:
        timings[name] = round((time.perf_counter() - t0) * 1000, 1)

    yield _ev("input", {"text": text, "input_type": input_type, "source_url": source_url})

    # 1) Claims ------------------------------------------------------------
    yield _ev("stage", {"stage": "claims", "status": "running", "detail": "Finding checkable claims"})
    t0 = time.perf_counter()
    try:
        extracted = await asyncio.wait_for(provider.extract_claims(text, s.max_claims), timeout=30)
    except Exception as e:  # noqa: BLE001
        log.warning("claim extraction failed: %r", e)
        if not isinstance(provider, HeuristicProvider):
            warnings.append(f"AI claim extraction failed ({type(e).__name__}); used sentence analysis instead.")
        extracted = heuristic_claims(text, s.max_claims)
    claims = [
        Claim(id=i, text=c.text, checkworthiness=c.checkworthiness, span=locate_span(text, c.quote, c.text))
        for i, c in enumerate(extracted)
    ]
    mark("claims", t0)
    yield _ev("claims", {"claims": [c.model_dump(mode="json") for c in claims]})
    yield _ev("stage", {"stage": "claims", "status": "done", "detail": f"{len(claims)} claim(s) found"})

    # 2) Language signals (fast, local) ------------------------------------
    t0 = time.perf_counter()
    tactics, tactics_score = detect_tactics(text)
    yield _ev("tactics", {"tactics": [t.model_dump(mode="json") for t in tactics], "score": tactics_score})
    style = await asyncio.to_thread(style_signal, text)
    yield _ev("style", style)
    mark("signals", t0)

    # 3) Evidence + verification, claims in parallel -------------------------
    results: dict[int, ClaimResult] = {}
    if claims:
        detail = "Searching sources and weighing evidence" if use_web else "Checking without web search"
        yield _ev("stage", {"stage": "verify", "status": "running", "detail": detail})
        t0 = time.perf_counter()
        tasks = {asyncio.create_task(_check_claim(c, text, use_web, warnings, sources_used)): c for c in claims}
        remaining = max(5.0, deadline - time.perf_counter())
        try:
            for fut in asyncio.as_completed(list(tasks), timeout=remaining):
                r = await fut
                results[r.claim.id] = r
                yield _ev("claim_result", r)
        except TimeoutError:
            warnings.append("Some claims took too long to check and were marked unverifiable.")
            for task, c in tasks.items():
                if c.id not in results:
                    task.cancel()
                    r = ClaimResult(
                        claim=c,
                        verdict="UNVERIFIABLE",
                        confidence=0.0,
                        reasoning="Checking timed out before enough evidence was gathered.",
                    )
                    results[c.id] = r
                    yield _ev("claim_result", r)
        mark("verify", t0)
        yield _ev("stage", {"stage": "verify", "status": "done", "detail": "Evidence weighed"})
    else:
        yield _ev("stage", {"stage": "verify", "status": "skipped", "detail": "No claims to check"})

    claim_results = [results[c.id] for c in claims]

    # 4) Aggregate + summary ------------------------------------------------
    yield _ev("stage", {"stage": "summary", "status": "running", "detail": "Writing the verdict"})
    t0 = time.perf_counter()
    overall, risk, confidence = aggregate(claim_results, tactics_score, style)
    headline, summary = HEADLINES[overall], default_summary(overall, claim_results, tactics)
    if claim_results and deadline - time.perf_counter() > 3:
        payload = "\n".join(
            [f"Overall: {overall}"]
            + [
                f"- Claim: {r.claim.text}\n  Verdict: {r.verdict} ({r.confidence:.0%})\n  Why: {r.reasoning}"
                for r in claim_results
            ]
            + ([f"Persuasion tactics in wording: {', '.join(t.name for t in tactics[:4])}"] if tactics else [])
        )
        try:
            got = await asyncio.wait_for(provider.summarize(payload), timeout=min(15, deadline - time.perf_counter()))
            if got:
                headline, summary = got
        except Exception as e:  # noqa: BLE001
            log.info("summary fallback: %r", e)
    if source_url and is_satire(source_url):
        warnings.append("This link is from a known satire site. It is meant as a joke, not news.")
    mark("summary", t0)
    timings["total"] = round((time.perf_counter() - started) * 1000, 1)

    result = AnalysisResult(
        id=uuid.uuid4().hex[:12],
        created_at=datetime.now(UTC),
        input_type=input_type,  # type: ignore[arg-type]
        input_preview=text[:280],
        input_text=text,
        source_url=source_url,
        extracted_text=extracted_text,
        overall=overall,
        headline=headline,
        summary=summary,
        guidance=GUIDANCE[overall],
        risk=risk,
        confidence=confidence,
        claims=claim_results,
        tactics=tactics,
        tactics_score=tactics_score,
        style=style,
        pipeline=PipelineInfo(
            llm_provider=provider.name,
            llm_model=provider.model,
            sources_used=sorted(sources_used),
            timings_ms=timings,
            warnings=warnings,
        ),
    )
    yield _ev("stage", {"stage": "summary", "status": "done", "detail": "Done"})
    yield _ev("result", result)


async def analyze(text: str, **kw) -> AnalysisResult:
    """Non-streaming convenience wrapper."""
    final = None
    async for e in run_analysis(text, **kw):
        if e["event"] == "result":
            final = e["data"]
    assert final is not None
    return AnalysisResult.model_validate(final)

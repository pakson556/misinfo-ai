"""
The conductor: runs every step of a check in order and reports progress as it goes.

THE STEPS (each one lives in its own file)
    0. input      send the text straight back, so the page can show it immediately
    1. claims     find the checkable claims            -> llm/ (Claude, Ollama or rules)
    2. signals    persuasion tactics + style model     -> tactics.py, style.py   (instant, local)
    3. verify     for EACH claim, at the same time:
                    a. gather evidence                 -> retrieval.py
                    b. judge the claim vs the evidence -> llm/
    4. summary    combine into one verdict             -> aggregate.py
                  + a short headline/summary           -> llm/

STREAMING
    run_analysis() is an *async generator*: instead of returning one value at
    the end, it `yield`s small events while it works. main.py forwards each one
    to the browser, which is why the page fills in step by step.

    The events, in order (each is a dict {"event": name, "data": ...}):
  input         {"text": str, "input_type": str, "source_url": str|None}
  stage         {"stage": str, "status": "running"|"done"|"skipped", "detail": str}
  claims        {"claims": [Claim]}
  tactics       {"tactics": [Tactic], "score": float}
  style         StyleSignal
  claim_result  ClaimResult
  result        AnalysisResult
  error         {"message": str}

NOTHING HERE IS ALLOWED TO CRASH THE CHECK
    If the AI fails, we fall back to simpler methods. If a claim takes too long,
    it's marked "unverifiable". Problems are added to `warnings`, which the page
    shows in amber, instead of the whole check failing.
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
    """Package one progress event. Pydantic objects are turned into plain JSON-ready dicts."""
    if hasattr(data, "model_dump"):
        data = data.model_dump(mode="json")
    return {"event": event, "data": data}


def locate_span(text: str, quote: str, claim: str) -> Span | None:
    """
    Find where a claim came from in the original text, so the page can highlight it.

    The AI gives back a `quote` (the exact words it took the claim from) and the
    rewritten `claim`. Try an exact (case-insensitive) search for each first.
    If the AI changed the wording slightly, fall back to fuzzy matching.
    Returns None if nothing matches well enough (the claim is then listed but not highlighted).
    """
    for needle in (quote, claim):
        needle = (needle or "").strip()
        if len(needle) < 6:
            continue
        i = text.lower().find(needle.lower())
        if i >= 0:
            return Span(start=i, end=i + len(needle), text=text[i : i + len(needle)])
    # Fuzzy: slide a window along the text in 20-character steps and keep the
    # position that looks most like the quote (score 0-100; 80+ counts as a match).
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
    """
    Check ONE claim: gather evidence, ask the AI for a verdict, tidy up the sources.

    run_analysis() starts one of these per claim and runs them at the same time,
    so 5 claims take about as long as the slowest one, not 5x as long.
    `warnings` and `sources_used` are shared lists that every claim adds to.
    """
    provider = get_provider()
    evidence: list[Evidence] = []
    # a) Evidence from Google Fact Check, Wikipedia, etc. (skipped if "Search the web" is unticked)
    if use_web:
        evidence, used, warns = await gather_evidence(claim.text)
        sources_used.update(used)
        warnings.extend(w for w in warns if w not in warnings)

    # b) Verdict. If the AI call fails (network, API limit, ...), don't give up:
    #    fall back to matching published fact-checks.
    method = "llm" if not isinstance(provider, HeuristicProvider) else "factcheck_match"
    try:
        outcome = await provider.verify_claim(claim.text, evidence, context, allow_search=use_web)
    except Exception:  # noqa: BLE001
        log.exception("LLM verification failed")
        msg = "The AI couldn't check one of the facts, so published fact-checks were used for it instead."
        if msg not in warnings:
            warnings.append(msg)
        outcome = await HeuristicProvider().verify_claim(claim.text, evidence, context, use_web)
        method = "factcheck_match"

    # c) Record what the AI concluded about each source ("supports", "refutes", ...),
    #    and add any extra sources Claude found with its own web search.
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
    """
    Run a full check on `text`, yielding progress events (see the top of this file).

    use_web         search for evidence online (the checkbox on the page)
    input_type      "text", "url" or "image": only used for display/history
    source_url      the link, if the input came from one
    extracted_text  the OCR'd text, if the input was a screenshot
    """
    s = get_settings()
    provider = get_provider()  # Claude, Ollama or the no-AI fallback, depending on settings
    started = time.perf_counter()
    deadline = started + s.pipeline_budget_s  # hard time limit for the whole check
    timings: dict[str, float] = {}
    warnings: list[str] = []
    sources_used: set[str] = set()
    text = text.strip()[: s.max_input_chars]

    def mark(name: str, t0: float) -> None:
        """Record how many milliseconds a stage took (shown at the bottom of the result)."""
        timings[name] = round((time.perf_counter() - t0) * 1000, 1)

    yield _ev("input", {"text": text, "input_type": input_type, "source_url": source_url})

    # 1) Claims ------------------------------------------------------------
    yield _ev("stage", {"stage": "claims", "status": "running", "detail": "Finding the facts to check"})
    t0 = time.perf_counter()
    try:
        # Ask the AI to list the checkable claims (gives up after 30 seconds).
        extracted = await asyncio.wait_for(provider.extract_claims(text, s.max_claims), timeout=30)
    except Exception as e:  # noqa: BLE001
        # AI unavailable -> pick out factual-looking sentences with simple rules instead.
        log.warning("claim extraction failed: %r", e)
        if not isinstance(provider, HeuristicProvider):
            warnings.append("The AI couldn't read the text this time, so it was checked sentence by sentence instead.")
        extracted = heuristic_claims(text, s.max_claims)
    claims = [
        Claim(id=i, text=c.text, checkworthiness=c.checkworthiness, span=locate_span(text, c.quote, c.text))
        for i, c in enumerate(extracted)
    ]
    mark("claims", t0)
    yield _ev("claims", {"claims": [c.model_dump(mode="json") for c in claims]})
    yield _ev(
        "stage",
        {"stage": "claims", "status": "done", "detail": f"Found {len(claims)} fact{'s' if len(claims) != 1 else ''} to check"},
    )

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
        detail = "Looking them up in trusted sources" if use_web else "Looking them up (without web search)"
        yield _ev("stage", {"stage": "verify", "status": "running", "detail": detail})
        t0 = time.perf_counter()
        # Start checking every claim at once (each is an asyncio "task" running in parallel).
        tasks = {asyncio.create_task(_check_claim(c, text, use_web, warnings, sources_used)): c for c in claims}
        remaining = max(5.0, deadline - time.perf_counter())
        try:
            # as_completed hands back each claim the moment it finishes, in whatever order
            # they finish, so a quick claim turns green/red without waiting for slow ones.
            for fut in asyncio.as_completed(list(tasks), timeout=remaining):
                r = await fut
                results[r.claim.id] = r
                yield _ev("claim_result", r)
        except TimeoutError:
            # Out of time: stop the unfinished claims and mark them unverifiable.
            warnings.append("Some facts took too long to check, so they're marked \"Can't confirm\".")
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
        yield _ev("stage", {"stage": "verify", "status": "done", "detail": "Looked them up"})
    else:
        yield _ev("stage", {"stage": "verify", "status": "skipped", "detail": "No facts to check"})

    claim_results = [results[c.id] for c in claims]

    # 4) Aggregate + summary ------------------------------------------------
    yield _ev("stage", {"stage": "summary", "status": "running", "detail": "Writing the answer"})
    t0 = time.perf_counter()
    # Combine everything into one overall verdict + risk + confidence (the maths is in aggregate.py).
    overall, risk, confidence = aggregate(claim_results, tactics_score, style)
    # Start with a ready-made headline and summary, then ask the AI for a nicer one if time allows.
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
        warnings.append("This link is from a joke news website. It isn't meant to be real news.")
    mark("summary", t0)
    timings["total"] = round((time.perf_counter() - started) * 1000, 1)

    # Package the final answer (shape defined in schemas.py).
    result = AnalysisResult(
        id=uuid.uuid4().hex[:12],  # random 12-character id, used in /a/<id> share links
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
    """Run a check and just return the final result (no streaming). Handy in scripts and notebooks."""
    final = None
    async for e in run_analysis(text, **kw):
        if e["event"] == "result":
            final = e["data"]
    assert final is not None
    return AnalysisResult.model_validate(final)

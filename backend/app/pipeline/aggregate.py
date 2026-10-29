"""Combine claim verdicts, tactics and style into one judgement.

Design:
- Evidence about claims decides the verdict. Nothing else can make content "false".
- Tactics and style form a weak *prior* that only fills the gap where evidence is
  missing, weighted by (1 - evidence coverage).
- Confidence = how much of the important content is backed by evidence, so a
  verdict based only on wording can never look confident.
"""

from __future__ import annotations

from ..schemas import ClaimResult, Overall, StyleSignal, Tactic

FALSITY = {"REFUTED": 1.0, "MIXED": 0.55, "SUPPORTED": 0.0}


def _prior(tactics_score: float, style: StyleSignal) -> float:
    p = 0.2 + 0.4 * tactics_score
    if style.available and style.probability is not None:
        p += 0.25 * (style.probability - 0.5)
    return max(0.03, min(0.85, p))


def aggregate(claims: list[ClaimResult], tactics_score: float, style: StyleSignal) -> tuple[Overall, float, float]:
    """Return (overall, risk 0..1, confidence 0..1)."""
    prior = _prior(tactics_score, style)
    if not claims:
        return "NO_CLAIMS", round(prior, 3), round(min(0.3, 0.1 + 0.3 * tactics_score), 3)

    total_w = sum(max(0.1, c.claim.checkworthiness) for c in claims)
    ev_num = ev_den = covered = 0.0
    for c in claims:
        w = max(0.1, c.claim.checkworthiness)
        f = FALSITY.get(c.verdict)
        if f is None:
            continue
        ev_num += w * c.confidence * f
        ev_den += w * c.confidence
        covered += w * c.confidence

    coverage = covered / total_w if total_w else 0.0
    evidence_risk = ev_num / ev_den if ev_den else prior
    risk = coverage * evidence_risk + (1 - coverage) * prior

    important = [c for c in claims if c.claim.checkworthiness >= 0.4] or claims
    strong_false = any(c.verdict == "REFUTED" and c.confidence >= 0.6 for c in important)
    any_false = any(c.verdict == "REFUTED" for c in claims)
    any_mixed = any(c.verdict == "MIXED" for c in claims)
    verifiable = [c for c in claims if c.verdict != "UNVERIFIABLE"]

    if strong_false:
        overall: Overall = "LIKELY_FALSE"
        risk = max(risk, 0.7)
    elif any_false or any_mixed:
        overall = "NEEDS_CONTEXT"
        risk = max(risk, 0.4)
    elif verifiable and all(c.verdict == "SUPPORTED" for c in verifiable) and coverage >= 0.45:
        overall = "LOOKS_RELIABLE"
    else:
        overall = "UNVERIFIED"

    confidence = 0.1 + 0.85 * coverage
    return overall, round(min(0.99, max(0.01, risk)), 3), round(min(0.95, confidence), 3)


HEADLINES = {
    "LIKELY_FALSE": "Contains claims that reliable sources contradict",
    "NEEDS_CONTEXT": "Partly accurate, but missing context or disputed",
    "LOOKS_RELIABLE": "Key claims are backed by reliable sources",
    "UNVERIFIED": "Couldn't confirm or rule out the main claims",
    "NO_CLAIMS": "No checkable factual claims found",
}

GUIDANCE = {
    "LIKELY_FALSE": "Don't share this as fact. If you want to respond, link the sources below rather than repeating the claim.",
    "NEEDS_CONTEXT": "Read the details below before sharing, and add the missing context if you do.",
    "LOOKS_RELIABLE": "The checked claims hold up. It's still worth opening a source or two, especially for fast-moving news.",
    "UNVERIFIED": "Treat this as unconfirmed. Look for a primary source (official statement, study or original report) before sharing.",
    "NO_CLAIMS": "This reads as opinion or commentary rather than factual claims, so there's nothing to fact-check. Judge it on its arguments.",
}


def default_summary(overall: Overall, claims: list[ClaimResult], tactics: list[Tactic]) -> str:
    counts = {v: sum(c.verdict == v for c in claims) for v in ("SUPPORTED", "REFUTED", "MIXED", "UNVERIFIABLE")}
    parts = []
    if claims:
        bits = []
        if counts["REFUTED"]:
            bits.append(f"{counts['REFUTED']} contradicted by evidence")
        if counts["MIXED"]:
            bits.append(f"{counts['MIXED']} partly true or missing context")
        if counts["SUPPORTED"]:
            bits.append(f"{counts['SUPPORTED']} supported")
        if counts["UNVERIFIABLE"]:
            bits.append(f"{counts['UNVERIFIABLE']} could not be verified")
        parts.append(f"We checked {len(claims)} claim{'s' if len(claims) != 1 else ''}: " + ", ".join(bits) + ".")
        worst = next((c for c in claims if c.verdict == "REFUTED"), None) or next(
            (c for c in claims if c.verdict == "MIXED"), None
        )
        if worst and worst.reasoning:
            parts.append(worst.reasoning.split(". ")[0].rstrip(".") + ".")
    if tactics:
        names = ", ".join(t.name.lower() for t in tactics[:3])
        parts.append(f"The wording also uses persuasion tactics ({names}).")
    return " ".join(parts) or HEADLINES[overall] + "."

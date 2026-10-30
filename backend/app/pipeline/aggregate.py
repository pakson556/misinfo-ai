"""
Turns the individual claim verdicts into one overall verdict, risk and confidence.

THE RULES
    1. Evidence decides. Only claims that reliable sources contradict can make
       content "Likely false". Scary wording alone never can.
    2. Wording (tactics) and the style model are a weak *starting guess* ("prior")
       that only fills the gap where evidence is missing.
    3. Confidence = how much of the important content is actually backed by
       evidence. A verdict based only on wording can never look confident.

WORKED EXAMPLE
    Two claims, both very checkworthy (weight 0.9):
      claim A: REFUTED,      confidence 0.9  -> strong evidence it's false
      claim B: UNVERIFIABLE, confidence 0.1  -> no evidence either way
    coverage = (0.9*0.9) / (0.9+0.9) = 0.45    (45% of the content is evidence-backed)
    evidence_risk = 1.0                         (all the evidence that exists says "false")
    risk = 0.45*1.0 + 0.55*prior                (the rest falls back to the wording guess)
    A is a strong, important REFUTED claim -> overall = LIKELY_FALSE, risk at least 0.7.
"""

from __future__ import annotations

from ..schemas import ClaimResult, Overall, StyleSignal, Tactic

# How "false" each verdict is, from 0 (true) to 1 (false). UNVERIFIABLE is missing
# on purpose: no evidence means it shouldn't count either way.
FALSITY = {"REFUTED": 1.0, "MIXED": 0.55, "SUPPORTED": 0.0}


def _prior(tactics_score: float, style: StyleSignal) -> float:
    """
    The starting guess, used only where evidence is missing.

    Starts at 0.2, rises with persuasion tactics (up to +0.4), and moves a little
    with the style model if one is installed. Always kept between 0.03 and 0.85
    so wording alone can't push it to the extremes.
    """
    p = 0.2 + 0.4 * tactics_score
    if style.available and style.probability is not None:
        p += 0.25 * (style.probability - 0.5)
    return max(0.03, min(0.85, p))


def aggregate(claims: list[ClaimResult], tactics_score: float, style: StyleSignal) -> tuple[Overall, float, float]:
    """Return (overall verdict, risk 0..1, confidence 0..1). See the worked example at the top."""
    prior = _prior(tactics_score, style)
    if not claims:
        # Nothing factual to check (opinion, a joke, ...): low confidence, risk from wording only.
        return "NO_CLAIMS", round(prior, 3), round(min(0.3, 0.1 + 0.3 * tactics_score), 3)

    # Each claim counts in proportion to how important it is (checkworthiness),
    # and its evidence counts in proportion to how confident the verdict is.
    total_w = sum(max(0.1, c.claim.checkworthiness) for c in claims)
    ev_num = ev_den = covered = 0.0
    for c in claims:
        w = max(0.1, c.claim.checkworthiness)
        f = FALSITY.get(c.verdict)
        if f is None:  # UNVERIFIABLE: contributes nothing
            continue
        ev_num += w * c.confidence * f
        ev_den += w * c.confidence
        covered += w * c.confidence

    coverage = covered / total_w if total_w else 0.0  # 0..1: share of content backed by evidence
    evidence_risk = ev_num / ev_den if ev_den else prior  # what the evidence says, on average
    # Blend: trust evidence for the part it covers, the prior for the rest.
    risk = coverage * evidence_risk + (1 - coverage) * prior

    # Pick the overall label. Only "important" claims (checkworthiness >= 0.4) can
    # make the whole text "Likely false", so a trivial side detail can't.
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

    confidence = 0.1 + 0.85 * coverage  # never 0 and never above 0.95: there's always some uncertainty
    return overall, round(min(0.99, max(0.01, risk)), 3), round(min(0.95, confidence), 3)


# Default wording per verdict. The AI can replace HEADLINES with its own summary; GUIDANCE is always used.
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
    """
    A plain summary built from the results, used when no AI is available (or it's slow).
    E.g. "We checked 2 claims: 1 contradicted by evidence, 1 supported. <reason>. The wording also uses ..."
    """
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
        # Quote the first sentence of the reasoning for the worst claim.
        worst = next((c for c in claims if c.verdict == "REFUTED"), None) or next(
            (c for c in claims if c.verdict == "MIXED"), None
        )
        if worst and worst.reasoning:
            parts.append(worst.reasoning.split(". ")[0].rstrip(".") + ".")
    if tactics:
        names = ", ".join(t.name.lower() for t in tactics[:3])
        parts.append(f"The wording also uses persuasion tactics ({names}).")
    return " ".join(parts) or HEADLINES[overall] + "."

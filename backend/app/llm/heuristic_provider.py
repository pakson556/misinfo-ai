"""
The no-AI fallback. Used when no AI is configured, or when the AI fails mid-check.

FINDING CLAIMS: simple sentence rules
    Split into sentences, then score each: has a factual verb ("is", "causes",
    "announced"...)? numbers? names? Opinion words ("I think", "should") lower the
    score. The highest-scoring sentences become claims.

JUDGING CLAIMS: only by matching published fact-checks
    If Google Fact Check returned a review of a very similar claim, use the
    fact-checker's rating ("False" -> REFUTED). Otherwise: UNVERIFIABLE.
    It never guesses. That's why, with no keys at all, most claims come back "Unverified".
"""

from __future__ import annotations

import re

from rapidfuzz import fuzz

from ..schemas import Evidence
from .base import ExtractedClaim, VerifyOutcome

# Sentence boundaries: after . ! ? followed by a capital letter or quote, or at a line break.
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'“])|\n+")
# Words that mark opinion or calls to action rather than factual claims.
_OPINION = re.compile(r"\b(i think|i believe|i feel|in my opinion|imo|should|must|let's|please|we need to)\b", re.I)
# Verbs typical of factual statements.
_FACTUAL = re.compile(
    r"\b(is|are|was|were|has|have|had|causes?|caused|cures?|kills?|killed|contains?|found|shows?|"
    r"announced|confirmed|said|says|reported|banned|approved|increased|decreased|died|will)\b",
    re.I,
)
_NUMBER = re.compile(r"\d")
# A capitalised word that isn't at the start of a sentence: probably a name or place.
_PROPER = re.compile(r"(?<!^)(?<![.!?]\s)\b[A-Z][a-z]{2,}")


def heuristic_claims(text: str, max_claims: int) -> list[ExtractedClaim]:
    """Pick the most claim-like sentences (see the scoring described at the top of this file)."""
    scored = []
    for raw in _SENT_SPLIT.split(text):
        s = raw.strip(" -•*\t\"'")
        words = s.split()
        if len(words) < 5 or len(words) > 60 or s.endswith("?"):
            continue
        score = 0.25
        if _FACTUAL.search(s):
            score += 0.25
        if _NUMBER.search(s):
            score += 0.2
        if _PROPER.search(s):
            score += 0.15
        if _OPINION.search(s):
            score -= 0.3
        if score >= 0.45:
            scored.append(ExtractedClaim(text=s, quote=raw.strip(), checkworthiness=round(min(1.0, score), 2)))
    scored.sort(key=lambda c: c.checkworthiness, reverse=True)
    seen, out = set(), []
    for c in scored:
        key = c.text.lower()[:80]
        if key not in seen:
            seen.add(key)
            out.append(c)
    return out[:max_claims]


# Words fact-checkers use in their ratings, grouped by meaning.
FALSE_WORDS = (
    "false",
    "fake",
    "hoax",
    "pants on fire",
    "incorrect",
    "wrong",
    "fabricated",
    "baseless",
    "no evidence",
    "untrue",
    "scam",
    "debunked",
    "not true",
    "misattributed",
    "four pinocchios",
    "falso",
)
MIXED_WORDS = (
    "misleading",
    "mixed",
    "half true",
    "half-true",
    "partly",
    "partially",
    "missing context",
    "out of context",
    "exaggerat",
    "unproven",
    "needs context",
    "distorts",
    "satire",
    "mostly true",
)
TRUE_WORDS = ("true", "correct", "accurate", "verdadero")


def rating_to_verdict(rating: str) -> str:
    """Translate a fact-checker's rating ("Pants on Fire!", "Half True", ...) into our 4 verdicts."""
    r = (rating or "").lower()
    if "mostly false" in r or "pants on fire" in r:
        return "REFUTED"
    if any(w in r for w in MIXED_WORDS):
        return "MIXED"
    if any(w in r for w in FALSE_WORDS):
        return "REFUTED"
    if any(w in r for w in TRUE_WORDS):
        return "SUPPORTED"
    return "UNVERIFIABLE"


def match_factchecks(claim: str, evidence: list[Evidence]) -> list[tuple[int, Evidence, float]]:
    """Fact-checks whose reviewed claim text is close to ours, best first."""
    out = []
    for i, e in enumerate(evidence):
        if e.kind != "factcheck" or not e.rating:
            continue
        sim = fuzz.token_set_ratio(claim.lower(), (e.snippet or e.title).lower()) / 100
        if sim >= 0.6:
            out.append((i, e, sim))
    return sorted(out, key=lambda x: x[2], reverse=True)


class HeuristicProvider:
    """The no-AI provider. Same three methods as the AI providers (see llm/__init__.py)."""

    name = "none"
    model = None
    can_search = False

    async def extract_claims(self, text: str, max_claims: int) -> list[ExtractedClaim]:
        return heuristic_claims(text, max_claims)

    async def verify_claim(self, claim: str, evidence: list[Evidence], context: str, allow_search: bool) -> VerifyOutcome:
        matches = match_factchecks(claim, evidence)
        if not matches:
            return VerifyOutcome(
                verdict="UNVERIFIABLE",
                confidence=0.15,
                reasoning="No published fact-check closely matches this claim, and no AI reasoning model is configured to weigh other evidence.",
            )
        # Several fact-checks may match: each 'votes' for its verdict, weighted by
        # how similar its claim is to ours and how trusted the fact-checker is.
        votes: dict[str, float] = {}
        stances = {}
        for i, e, sim in matches[:5]:
            v = rating_to_verdict(e.rating or "")
            votes[v] = votes.get(v, 0) + sim * e.credibility
            stances[i] = {"REFUTED": "refutes", "SUPPORTED": "supports", "MIXED": "mixed"}.get(v, "neutral")
        verdict = max(votes, key=votes.get)
        total = sum(votes.values())
        best = matches[0][1]
        conf = min(0.85, 0.35 + 0.5 * (votes[verdict] / total) * matches[0][2])
        return VerifyOutcome(
            verdict=verdict,
            confidence=round(conf, 2),
            stances=stances,
            reasoning=f"{best.publisher or best.domain} reviewed a closely matching claim and rated it “{best.rating}”.",
        )

    async def summarize(self, payload: str):
        return None

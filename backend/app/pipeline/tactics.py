"""
Persuasion-tactic detection: the "How it's written" panel and the dotted underlines.

WHAT IT DOES
    Scans the text for phrases that pressure people ("share before they delete
    it!"), stir up emotion ("SHOCKING"), or lean on fake authority ("a nurse
    told me"). Each match is recorded with its exact position so the website
    can underline it.

WHY IT DOESN'T DECIDE THE VERDICT
    Tactics describe *how* a text tries to persuade, not whether it is true.
    True content can use urgent language and false content can be calm, so
    tactics only nudge the risk score when evidence is missing (see aggregate.py).

WHERE THE CATEGORIES COME FROM
    The manipulation techniques used in "inoculation" research (Roozenbeek &
    van der Linden, e.g. the "Bad News" and "Go Viral!" games), plus common
    social-media signals.

PURE PYTHON, NO AI
    This runs locally in milliseconds with regular expressions (regex), so it
    works even with no API keys. Every pattern uses word boundaries (\\b), so
    "ai" does not match "said" and "pass" does not match "passed" (a v1 bug).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..schemas import Span, Tactic


@dataclass(frozen=True)
class TacticDef:
    """The definition of one tactic. To add a new tactic, add a TacticDef to TACTICS below."""

    id: str  # internal name, stored in the database
    name: str  # shown in the UI
    description: str  # shown under the name
    weight: float  # 0..1, how strong a signal this tactic is (conspiracy framing > absolutes)
    patterns: tuple[str, ...]  # regular expressions to search for


def _w(*words: str) -> tuple[str, ...]:
    """
    Turn plain phrases into safe whole-word regex patterns.

    "don't wait" becomes \\bdon['’]t\\s+wait\\b, which:
      - only matches whole words (\\b = word boundary),
      - accepts straight ' and curly ’ apostrophes (phones type curly ones),
      - accepts any amount of whitespace between words.
    """
    out = []
    for w in words:
        p = re.escape(w).replace("\\ ", r"\s+").replace("'", "['’]")
        out.append(rf"\b{p}\b")
    return tuple(out)


# The full list of tactics. Matching ignores upper/lower case.
TACTICS: tuple[TacticDef, ...] = (
    TacticDef(
        "virality_call",
        "Pressure to share",
        "Tells you to pass it on before you've had time to check it.",
        0.8,
        _w(
            "share this",
            "share before",
            "share widely",
            "please share",
            "spread the word",
            "pass it on",
            "pass this on",
            "forward this",
            "forward to everyone",
            "tell everyone",
            "send this to",
            "copy and paste",
            "make this go viral",
            "repost",
            "retweet this",
            "before they delete",
            "before it gets deleted",
            "before it's taken down",
            "before it gets banned",
        ),
    ),
    TacticDef(
        "urgency",
        "Rushing you",
        "Says you must act right now, so you don't stop and think.",
        0.5,
        _w(
            "breaking",
            "urgent",
            "act now",
            "right now",
            "immediately",
            "before it's too late",
            "last chance",
            "time is running out",
            "don't wait",
            "happening now",
            "just in",
        ),
    ),
    TacticDef(
        "conspiracy",
        "Cover-up story",
        "Claims powerful people are hiding the truth from you.",
        0.9,
        _w(
            "they don't want you to know",
            "what they don't want you to know",
            "they're hiding",
            "they are hiding",
            "cover up",
            "cover-up",
            "covered up",
            "hidden truth",
            "the real truth",
            "wake up",
            "sheeple",
            "deep state",
            "new world order",
            "globalists",
            "plandemic",
            "scamdemic",
            "mainstream media won't",
            "the media won't tell you",
            "msm won't",
            "suppressed",
            "silenced",
            "censored",
            "banned video",
            "they lied",
            "open your eyes",
            "do your own research",
            "big pharma",
            "controlled opposition",
            "false flag",
            "agenda 21",
            "great reset",
        ),
    ),
    TacticDef(
        "false_authority",
        "Vague experts",
        'Quotes unnamed "doctors" or "insiders" instead of real sources you can check.',
        0.6,
        _w(
            "insiders say",
            "an insider",
            "a friend who works",
            "my cousin who is a",
            "doctors are saying",
            "scientists are saying",
            "experts agree",
            "sources say",
            "100% confirmed",
            "confirmed by insiders",
            "i know for a fact",
            "trust me",
            "a nurse told me",
            "leaked document",
            "whistleblower reveals",
            "studies show",
            "research proves",
            "science proves",
        ),
    ),
    TacticDef(
        "emotional",
        "Scary or angry words",
        "Uses words meant to frighten or anger you, so you react before thinking.",
        0.5,
        _w(
            "shocking",
            "horrifying",
            "terrifying",
            "outrageous",
            "disgusting",
            "evil",
            "sick",
            "chilling",
            "you won't believe",
            "jaw-dropping",
            "mind-blowing",
            "unbelievable",
            "nightmare",
            "catastrophe",
            "destroy",
            "destroyed",
            "deadly",
            "poison",
            "poisoning",
            "toxic",
            "genocide",
            "slaughter",
            "traitor",
            "traitors",
            "betrayal",
            "panic",
            "terrified",
            "outrage",
            "enraged",
            "heartbreaking",
        ),
    ),
    TacticDef(
        "absolutes",
        "Too sure of itself",
        'Uses words like "always", "100%" or "proven". Real evidence is rarely that certain.',
        0.35,
        _w(
            "100%",
            "guaranteed",
            "proven fact",
            "undeniable",
            "everyone knows",
            "no one is talking about",
            "nobody is talking about",
            "always",
            "never",
            "completely safe",
            "totally safe",
            "instantly cures",
            "cures all",
            "miracle",
            "the only way",
            "no doubt",
        ),
    ),
    TacticDef(
        "scapegoating",
        "Blaming a group",
        "Blames a whole group of people for a complicated problem.",
        0.7,
        _w(
            "it's all their fault",
            "they are to blame",
            "these people",
            "those people",
            "invaders",
            "flooding our country",
            "replacing us",
            "the elites",
            "the globalists are",
        ),
    ),
    TacticDef(
        "false_dichotomy",
        "Only two choices",
        "Pretends there are only two options when there are more.",
        0.4,
        _w("either you", "you're either with us", "if you don't", "only two options", "there is no middle", "you can either"),
    ),
    TacticDef(
        "miracle_health",
        "Miracle cure",
        "Promises a secret or simple cure. A classic sign of false health news.",
        0.8,
        _w(
            "secret cure",
            "miracle cure",
            "cures cancer",
            "kills cancer",
            "doctors hate",
            "one weird trick",
            "natural cure",
            "detox",
            "boost your immune system",
            "they won't tell you about this cure",
            "cure for",
            "reverses diabetes",
            "the cure they",
            "kills the virus",
        ),
    ),
)

# Two tactics are detected by shape rather than by phrase:
_CAPS_WORD = re.compile(r"\b[A-Z]{4,}\b")  # a word of 4+ capital letters ("BREAKING")
_MULTI_PUNCT = re.compile(r"[!?]{2,}")  # "!!!" or "?!?"
# Capitalised words that are normal acronyms, not shouting.
_ACRONYM_OK = {"NASA", "COVID", "NATO", "FIFA", "UEFA", "NHS", "HTTP", "HTTPS", "UNICEF", "WHO", "USA", "OPEC", "NIH"}

# Compile every pattern once when the server starts (compiling on every request would be slow).
_COMPILED = [(t, [re.compile(p, re.IGNORECASE) for p in t.patterns]) for t in TACTICS]

# id -> display name, including the two shape-based tactics. Used by the Insights page (db.py).
TACTIC_NAMES = {t.id: t.name for t in TACTICS} | {
    "shouting": "Shouting (ALL CAPS)",
    "excess_punctuation": "Too many !!! or ???",
}


def _merge_spans(spans: list[Span]) -> list[Span]:
    """
    Combine overlapping matches into one highlight.

    E.g. "share this" and "share this before they delete" both match the same
    words; we want one underline, not two stacked on top of each other.
    """
    spans = sorted(spans, key=lambda s: (s.start, -s.end))
    out: list[Span] = []
    for s in spans:
        if out and s.start <= out[-1].end:
            if s.end > out[-1].end:
                last = out[-1]
                out[-1] = Span(start=last.start, end=s.end, text=last.text + s.text[last.end - s.start :])
            continue
        out.append(s)
    return out


def detect_tactics(text: str) -> tuple[list[Tactic], float]:
    """
    Find every tactic in `text`.

    Returns (tactics, score):
      tactics  list of Tactic, strongest first, each with the exact places it appears
      score    0..1 overall "how hard is this pushing" number
    """
    found: list[Tactic] = []
    words = max(1, len(text.split()))

    # 1) Phrase-based tactics
    for t, regexes in _COMPILED:
        spans = [Span(start=m.start(), end=m.end(), text=m.group(0)) for rx in regexes for m in rx.finditer(text)]
        if not spans:
            continue
        spans = _merge_spans(spans)
        # Severity grows with repetition but saturates; dense use in short text counts more.
        density = len(spans) / (words / 50 + 1)
        severity = min(1.0, t.weight * (0.6 + 0.4 * min(1.0, density / 2)))
        found.append(Tactic(id=t.id, name=t.name, description=t.description, severity=round(severity, 3), spans=spans[:12]))

    # 2) Shouting: several ALL-CAPS words, or a text that is mostly capitals
    caps = [m for m in _CAPS_WORD.finditer(text) if m.group(0) not in _ACRONYM_OK]
    letters = sum(c.isalpha() for c in text) or 1
    caps_ratio = sum(c.isupper() for c in text) / letters
    if len(caps) >= 3 or (caps_ratio > 0.35 and letters > 40):
        found.append(
            Tactic(
                id="shouting",
                name="Shouting (ALL CAPS)",
                description="Lots of capital letters to sound alarming.",
                severity=round(min(0.6, 0.25 + 0.05 * len(caps)), 3),
                spans=[Span(start=m.start(), end=m.end(), text=m.group(0)) for m in caps[:12]],
            )
        )

    # 3) Excessive punctuation
    punct = list(_MULTI_PUNCT.finditer(text))
    if punct:
        found.append(
            Tactic(
                id="excess_punctuation",
                name="Too many !!! or ???",
                description="Used to make you feel excited or alarmed.",
                severity=round(min(0.4, 0.15 + 0.05 * len(punct)), 3),
                spans=[Span(start=m.start(), end=m.end(), text=m.group(0)) for m in punct[:12]],
            )
        )

    found.sort(key=lambda t: t.severity, reverse=True)
    # Combine into one score with "noisy-OR": several weak signals add up, but the
    # total can never go above 1. E.g. two tactics of severity 0.5 give
    # 1 - (1-0.35)*(1-0.35) = 0.58, not 1.0.
    score = 1.0
    for t in found:
        score *= 1 - t.severity * 0.7
    return found, round(1 - score, 3)

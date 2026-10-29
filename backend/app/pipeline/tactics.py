"""Manipulation-tactic detection.

Tactics describe *how* a text tries to persuade, not whether it is true. True
content can use urgent language and false content can be calm, so tactics only
nudge the overall risk; claim evidence decides it.

Categories follow the manipulation techniques used in inoculation research
(Roozenbeek & van der Linden, e.g. the "Bad News" / "Go Viral!" games) plus
common social-media signals. Every pattern uses word boundaries so "ai" does not
match "said" and "pass" does not match "passed".
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..schemas import Span, Tactic


@dataclass(frozen=True)
class TacticDef:
    id: str
    name: str
    description: str
    weight: float
    patterns: tuple[str, ...]


def _w(*words: str) -> tuple[str, ...]:
    """Whole-word/phrase patterns, tolerant of curly apostrophes and extra spaces."""
    out = []
    for w in words:
        p = re.escape(w).replace("\\ ", r"\s+").replace("'", "['’]")
        out.append(rf"\b{p}\b")
    return tuple(out)


TACTICS: tuple[TacticDef, ...] = (
    TacticDef(
        "virality_call",
        "Pressure to share",
        "Asks readers to spread the message before checking it.",
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
        "Artificial urgency",
        "Creates time pressure that discourages careful thinking.",
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
        "Conspiracy framing",
        "Suggests hidden powerful groups are concealing the truth.",
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
        "Vague or false authority",
        "Leans on unnamed insiders or unverifiable credentials instead of sources.",
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
        "Emotionally charged language",
        "Uses fear, outrage or shock words to trigger a reaction.",
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
        "Absolute certainty",
        "Claims total certainty, which real evidence rarely supports.",
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
        "Scapegoating",
        "Blames a whole group for a complex problem.",
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
        "False dilemma",
        "Presents only two options when more exist.",
        0.4,
        _w("either you", "you're either with us", "if you don't", "only two options", "there is no middle", "you can either"),
    ),
    TacticDef(
        "miracle_health",
        "Miracle health claim",
        "Promises cures or secret remedies, a hallmark of health misinformation.",
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

_CAPS_WORD = re.compile(r"\b[A-Z]{4,}\b")
_MULTI_PUNCT = re.compile(r"[!?]{2,}")
_ACRONYM_OK = {"NASA", "COVID", "NATO", "FIFA", "UEFA", "NHS", "HTTP", "HTTPS", "UNICEF", "WHO", "USA", "OPEC", "NIH"}

_COMPILED = [(t, [re.compile(p, re.IGNORECASE) for p in t.patterns]) for t in TACTICS]


def _merge_spans(spans: list[Span]) -> list[Span]:
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
    """Return detected tactics with highlighted spans and a 0..1 intensity score."""
    found: list[Tactic] = []
    words = max(1, len(text.split()))

    for t, regexes in _COMPILED:
        spans = [Span(start=m.start(), end=m.end(), text=m.group(0)) for rx in regexes for m in rx.finditer(text)]
        if not spans:
            continue
        spans = _merge_spans(spans)
        # Severity grows with repetition but saturates; dense use in short text counts more.
        density = len(spans) / (words / 50 + 1)
        severity = min(1.0, t.weight * (0.6 + 0.4 * min(1.0, density / 2)))
        found.append(Tactic(id=t.id, name=t.name, description=t.description, severity=round(severity, 3), spans=spans[:12]))

    caps = [m for m in _CAPS_WORD.finditer(text) if m.group(0) not in _ACRONYM_OK]
    letters = sum(c.isalpha() for c in text) or 1
    caps_ratio = sum(c.isupper() for c in text) / letters
    if len(caps) >= 3 or (caps_ratio > 0.35 and letters > 40):
        found.append(
            Tactic(
                id="shouting",
                name="Shouting (ALL CAPS)",
                description="Heavy use of capitals to signal alarm or anger.",
                severity=round(min(0.6, 0.25 + 0.05 * len(caps)), 3),
                spans=[Span(start=m.start(), end=m.end(), text=m.group(0)) for m in caps[:12]],
            )
        )

    punct = list(_MULTI_PUNCT.finditer(text))
    if punct:
        found.append(
            Tactic(
                id="excess_punctuation",
                name="Excessive punctuation",
                description="Repeated !!! or ??? to heighten emotion.",
                severity=round(min(0.4, 0.15 + 0.05 * len(punct)), 3),
                spans=[Span(start=m.start(), end=m.end(), text=m.group(0)) for m in punct[:12]],
            )
        )

    found.sort(key=lambda t: t.severity, reverse=True)
    # Noisy-OR: several independent weak signals add up, but never exceed 1.
    score = 1.0
    for t in found:
        score *= 1 - t.severity * 0.7
    return found, round(1 - score, 3)

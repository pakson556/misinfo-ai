"""Domain classification and credibility priors.

These are *priors*, not truth: a credible outlet can be wrong and an unknown blog
can be right. They are only used to weight evidence, never as a verdict on their own.
"""

from __future__ import annotations

from urllib.parse import urlparse

from ..schemas import SourceKind

FACTCHECKERS = {
    "snopes.com",
    "factcheck.org",
    "politifact.com",
    "fullfact.org",
    "leadstories.com",
    "factcheck.afp.com",
    "checkyourfact.com",
    "healthfeedback.org",
    "climatefeedback.org",
    "africacheck.org",
    "boomlive.in",
    "altnews.in",
    "maldita.es",
    "newtral.es",
    "correctiv.org",
    "logically.ai",
    "misbar.com",
    "ghanafact.com",
    "dubawa.org",
    "verafiles.org",
    "aap.com.au",
    "reuters.com/fact-check",
    "apnews.com/ap-fact-check",
    "bbc.co.uk/news/reality_check",
    "usatoday.com/news/factcheck",
    "washingtonpost.com/politics/fact-checker",
}

NEWS = {
    "reuters.com": 0.9,
    "apnews.com": 0.9,
    "bbc.co.uk": 0.88,
    "bbc.com": 0.88,
    "theguardian.com": 0.82,
    "npr.org": 0.85,
    "nytimes.com": 0.84,
    "wsj.com": 0.84,
    "ft.com": 0.85,
    "economist.com": 0.85,
    "washingtonpost.com": 0.82,
    "aljazeera.com": 0.78,
    "cnn.com": 0.76,
    "nbcnews.com": 0.78,
    "cbsnews.com": 0.78,
    "abcnews.go.com": 0.78,
    "independent.co.uk": 0.74,
    "sky.com": 0.78,
    "channel4.com": 0.8,
    "dw.com": 0.82,
    "france24.com": 0.8,
    "pbs.org": 0.85,
    "bloomberg.com": 0.84,
    "axios.com": 0.78,
    "politico.com": 0.78,
    "theconversation.com": 0.8,
    "scientificamerican.com": 0.84,
    "newscientist.com": 0.82,
    "nature.com": 0.92,
    "science.org": 0.92,
}

GOVERNMENT_SUFFIXES = (".gov", ".gov.uk", ".gov.au", ".gc.ca", ".gov.gh", ".europa.eu", ".mil")
GOVERNMENT_DOMAINS = {"who.int", "un.org", "nhs.uk", "ecdc.europa.eu", "ema.europa.eu", "ipcc.ch", "worldbank.org"}

SCIENCE_HINTS = (
    ".edu",
    ".ac.uk",
    ".ac.",
    "pubmed.ncbi.nlm.nih.gov",
    "ncbi.nlm.nih.gov",
    "arxiv.org",
    "sciencedirect.com",
    "springer.com",
    "wiley.com",
    "thelancet.com",
    "bmj.com",
    "nejm.org",
    "jamanetwork.com",
    "cochranelibrary.com",
    "plos.org",
)

ENCYCLOPEDIA = {"wikipedia.org": 0.75, "britannica.com": 0.85}

LOW_CRED = {
    "infowars.com",
    "naturalnews.com",
    "beforeitsnews.com",
    "theonion.com",
    "babylonbee.com",
    "worldtruth.tv",
    "yournewswire.com",
    "newspunch.com",
    "thegatewaypundit.com",
}
SATIRE = {"theonion.com", "babylonbee.com", "thedailymash.co.uk", "newsthump.com", "waterfordwhispersnews.com"}


def domain_of(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower()
    except ValueError:
        return ""
    return host[4:] if host.startswith("www.") else host


def _matches(host: str, path: str, entries) -> str | None:
    full = host + path
    for e in entries:
        if "/" in e:
            if full.startswith(e):
                return e
        elif host == e or host.endswith("." + e):
            return e
    return None


def classify(url: str) -> tuple[SourceKind, float]:
    """Return (kind, credibility prior in 0..1) for a URL."""
    host = domain_of(url)
    if not host:
        return "web", 0.4
    path = urlparse(url).path.lower()

    if _matches(host, path, LOW_CRED):
        return "web", 0.1
    if _matches(host, path, FACTCHECKERS):
        return "factcheck", 0.92
    if host.endswith(GOVERNMENT_SUFFIXES) or _matches(host, path, GOVERNMENT_DOMAINS):
        return "government", 0.88
    if any(h in host for h in SCIENCE_HINTS):
        return "science", 0.85
    m = _matches(host, path, NEWS)
    if m:
        return ("science" if m in {"nature.com", "science.org"} else "news"), NEWS[m]
    m = _matches(host, path, ENCYCLOPEDIA)
    if m:
        return "encyclopedia", ENCYCLOPEDIA[m]
    return "web", 0.45


def is_satire(url: str) -> bool:
    return bool(_matches(domain_of(url), "", SATIRE))

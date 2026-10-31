"""
Live monitor (first version): watch public Bluesky posts as they are written and
flag the ones that use common misinformation tricks.

HOW IT WORKS
  1. Connect to Bluesky's free public stream ("Jetstream"), no account needed.
     Every new public post arrives as a small JSON message.
  2. Keep English posts with enough text, and run the same warning-sign
     detector the Check page uses (tactics.py), plus the style model if installed.
  3. Posts with strong warning signs go into a short "recently flagged" list.
     Counters track how many posts were read and which tricks appear most.
  4. In the background, flagged posts are looked up in Google's database of
     published fact-checks (one every few seconds, to stay inside the free
     quota). If a fact-checker has reviewed a very similar claim, the post shows
     that fact-check, and the claim is counted in "Claims fact-checkers flagged".
  5. The Live page asks GET /api/monitor every few seconds and shows it.

PRIVACY (by design)
  Only the post's words are kept: no names, handles, account IDs or links.
  @mentions and web links are removed from the text, and nothing is written to
  disk: everything lives in memory and is gone when the server restarts.
  Being flagged is not a verdict. It only means "worth checking".

Switch it on with MONITOR_ENABLED=true in backend/.env.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from collections import Counter, deque
from datetime import UTC, datetime

from .config import get_settings
from .llm.heuristic_provider import heuristic_claims, match_factchecks, rating_to_verdict
from .pipeline.retrieval import google_factcheck
from .pipeline.style import style_signal
from .pipeline.tactics import detect_tactics

log = logging.getLogger(__name__)

# Bluesky's public servers. Tried in order; if one fails, the next is used.
STREAM_URLS = (
    "wss://jetstream2.us-east.bsky.network/subscribe?wantedCollections=app.bsky.feed.post",
    "wss://jetstream1.us-west.bsky.network/subscribe?wantedCollections=app.bsky.feed.post",
    "wss://jetstream.us-east.bsky.network/xrpc/network.bsky.jetstream.subscribeEvents"
    "?collections=app.bsky.feed.post&kinds=commit",
)

MIN_CHARS = 60  # shorter posts rarely contain a checkable claim
FLAG_SCORE = 0.3  # warning-sign strength (0-1) needed to be listed
KEEP_RECENT = 60  # how many flagged posts the Live page can show
# These signs are strong enough on their own (when the post also states a fact).
STRONG_TACTICS = {"miracle_health", "conspiracy", "false_authority"}
# Topics where misinformation is common. Other warning signs only count on these topics,
# so "please share my drawing!" isn't flagged but "please share: the vaccine causes ..." is.
TOPICS = re.compile(
    r"\b(vaccin\w*|jab|covid|virus|pandemic|cancer|cure[sd]?|doctor|hospital|nhs|pharma\w*|medic\w*|health|disease|"
    r"elect\w*|vot\w*|ballot|government|govt|minister|president|parliament|congress|senat\w*|"
    r"climate|weather|flood|wildfire|chemtrail\w*|5g|"
    r"war|army|military|missile|bomb\w*|attack\w*|refugee\w*|migrant\w*|immigra\w*|"
    r"police|crime|terror\w*|shooting|economy|inflation|tax\w*|bank\w*|crypto\w*|ai)\b",
    re.I,
)
# Capitals and "!!!" are common in sport, jokes and excitement, so on their own
# they never flag a post. At least one other warning sign must be present.
STYLE_ONLY = {"shouting", "excess_punctuation"}
LOOKUP_GAP_S = 3.0  # wait between fact-check lookups (about 1,200 an hour at most)
MATCH_MIN = 0.7  # how closely a fact-checked claim must match the post (0-1)

_MENTION = re.compile(r"@[\w.\-]+")
_URL = re.compile(r"https?://\S+|\b\w+\.(?:com|org|net|co|uk|io|ly|me|news)/\S*", re.I)


def extract_post(message: str) -> str | None:
    """
    Pull the text of a NEW English post out of one stream message, or None.
    Handles both message formats Bluesky uses (v1 and v2).
    """
    try:
        ev = json.loads(message)
    except ValueError:
        return None
    if "payload" in ev:  # v2 format
        p = ev["payload"]
        op, coll, record = p.get("operation"), p.get("collection"), p.get("record") or {}
    else:  # v1 format
        c = ev.get("commit") or {}
        op, coll, record = c.get("operation"), c.get("collection"), c.get("record") or {}
    if op != "create" or coll != "app.bsky.feed.post":
        return None
    if record.get("reply"):
        return None  # replies make little sense without the post they answer
    langs = record.get("langs") or []
    if langs and not any(str(lang).lower().startswith("en") for lang in langs):
        return None
    text = record.get("text") or ""
    # A picture, video or link with only a few words: the meaning is in the attachment,
    # which this text-only monitor can't see, so skip it.
    if record.get("embed") and len(text) < 160:
        return None
    return text if len(text) >= MIN_CHARS else None


def anonymise(text: str) -> str:
    """Remove @mentions and links, so no person or account can be identified from the list."""
    text = _URL.sub("[link]", _MENTION.sub("@someone", text))
    return re.sub(r"\s+", " ", text).strip()[:400]


class Monitor:
    """Counters and the recently-flagged list. One shared instance, kept in memory."""

    def __init__(self) -> None:
        self.started = datetime.now(UTC)
        self.connected = False
        self.source = ""
        self.seen = 0
        self.flagged = 0
        self.tactic_counts: Counter[str] = Counter()
        self.tactic_names: dict[str, str] = {}
        self.recent: deque[dict] = deque(maxlen=KEEP_RECENT)
        self.per_minute: deque[list] = deque(maxlen=60)  # [minute, posts read, posts flagged]
        # Fact-check lookups: a short waiting line of flagged posts, and what was found.
        self.queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=10)
        self.looked_up = 0
        self.matched = 0
        self.matched_claims: dict[str, dict] = {}  # fact-check URL -> claim, rating, how often seen

    def _tick(self, flagged: bool) -> None:
        minute = int(time.time() // 60)
        if not self.per_minute or self.per_minute[-1][0] != minute:
            self.per_minute.append([minute, 0, 0])
        self.per_minute[-1][1] += 1
        self.per_minute[-1][2] += int(flagged)

    def process(self, text: str) -> bool:
        """Score one post. Returns True if it was flagged."""
        self.seen += 1
        tactics, score = detect_tactics(text)
        content = {t.id for t in tactics} - STYLE_ONLY
        flagged = bool(content) and (bool(content & STRONG_TACTICS) or (score >= FLAG_SCORE and bool(TOPICS.search(text))))
        # Only posts that actually state something checkable (not just feelings, art or jokes).
        flagged = flagged and bool(heuristic_claims(text, 1))
        self._tick(flagged)
        if not flagged:
            return False
        self.flagged += 1
        for t in tactics:
            self.tactic_counts[t.id] += 1
            self.tactic_names[t.id] = t.name
        style = style_signal(text)
        item = {
            "text": anonymise(text),
            "tactics": [t.name for t in tactics],
            "strength": round(score, 2),
            "style": style.probability if style.available else None,
            "time": datetime.now(UTC).isoformat(timespec="seconds"),
            "factcheck": None,
        }
        self.recent.appendleft(item)
        if get_settings().google_factcheck_api_key and not self.queue.full():
            self.queue.put_nowait(item)  # the lookup fills item["factcheck"] in later
        return True

    async def lookup(self, item: dict) -> None:
        """Look one flagged post up in published fact-checks and attach the best close match."""
        self.looked_up += 1
        evidence = await google_factcheck(item["text"])
        matches = [m for m in match_factchecks(item["text"], evidence) if m[2] >= MATCH_MIN]
        if not matches:
            return
        _, e, sim = matches[0]
        fc = {
            "claim": e.snippet or e.title,
            "publisher": e.publisher or e.domain,
            "rating": e.rating,
            "verdict": rating_to_verdict(e.rating or ""),
            "url": e.url,
        }
        item["factcheck"] = fc
        self.matched += 1
        seen = self.matched_claims.setdefault(e.url, {**fc, "count": 0})
        seen["count"] += 1
        seen["last_seen"] = datetime.now(UTC).isoformat(timespec="seconds")

    def snapshot(self) -> dict:
        settings = get_settings()
        return {
            "enabled": settings.monitor_enabled,
            "connected": self.connected,
            "source": self.source,
            "started": self.started.isoformat(timespec="seconds"),
            "seen": self.seen,
            "flagged": self.flagged,
            "top_tactics": [
                {"id": k, "name": self.tactic_names.get(k, k), "count": v} for k, v in self.tactic_counts.most_common(8)
            ],
            "per_minute": [{"minute": m * 60, "seen": s, "flagged": f} for m, s, f in self.per_minute],
            "factcheck_enabled": bool(settings.google_factcheck_api_key),
            "looked_up": self.looked_up,
            "matched": self.matched,
            "matched_claims": sorted(self.matched_claims.values(), key=lambda c: (c["count"], c["last_seen"]), reverse=True)[:10],
            "recent": list(self.recent),
        }


monitor = Monitor()


async def lookup_forever() -> None:
    """Background task: take flagged posts from the waiting line and look them up, one at a time."""
    while True:
        item = await monitor.queue.get()
        try:
            await monitor.lookup(item)
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001 - a failed lookup just means no match shown
            log.warning("Fact-check lookup failed: %r", e)
        await asyncio.sleep(LOOKUP_GAP_S)


async def run_forever() -> None:
    """Background task: read the stream, and reconnect (trying the next server) if it drops."""
    import websockets  # installed with uvicorn[standard]

    worker = asyncio.create_task(lookup_forever())
    try:
        await _read_stream(websockets)
    finally:
        worker.cancel()


async def _read_stream(websockets) -> None:
    attempt = 0
    while True:
        url = STREAM_URLS[attempt % len(STREAM_URLS)]
        try:
            async with websockets.connect(url, ping_interval=20, max_size=2**20) as ws:
                monitor.connected, monitor.source = True, url.split("/")[2]
                log.info("Live monitor connected to %s", monitor.source)
                attempt = 0
                async for message in ws:
                    text = extract_post(message)
                    if text:
                        monitor.process(text)
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001 - network problems: wait and retry
            log.warning("Live monitor disconnected (%r); retrying", e)
        monitor.connected = False
        attempt += 1
        await asyncio.sleep(min(30, 2 * attempt))

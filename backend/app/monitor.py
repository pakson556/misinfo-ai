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
  4. The Live page asks GET /api/monitor every few seconds and shows it.

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
STRONG_TACTICS = {"miracle_health", "conspiracy", "virality_call"}

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
    langs = record.get("langs") or []
    if langs and not any(str(lang).lower().startswith("en") for lang in langs):
        return None
    text = record.get("text") or ""
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
        ids = {t.id for t in tactics}
        flagged = score >= FLAG_SCORE or bool(ids & STRONG_TACTICS)
        self._tick(flagged)
        if not flagged:
            return False
        self.flagged += 1
        for t in tactics:
            self.tactic_counts[t.id] += 1
            self.tactic_names[t.id] = t.name
        style = style_signal(text)
        self.recent.appendleft(
            {
                "text": anonymise(text),
                "tactics": [t.name for t in tactics],
                "strength": round(score, 2),
                "style": style.probability if style.available else None,
                "time": datetime.now(UTC).isoformat(timespec="seconds"),
            }
        )
        return True

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
            "recent": list(self.recent),
        }


monitor = Monitor()


async def run_forever() -> None:
    """Background task: read the stream, and reconnect (trying the next server) if it drops."""
    import websockets  # installed with uvicorn[standard]

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

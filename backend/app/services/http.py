"""
One shared way to call other websites' APIs, with caching.

WHY SHARED
    Opening a new connection for every request is slow. One shared
    httpx.AsyncClient reuses connections ("keep-alive") across all requests.

WHY CACHED
    If two people check the same claim, or you check it twice while testing,
    the second lookup comes from a local cache instead of calling Google or
    Wikipedia again. Faster, and it saves API quota. The cache is a folder
    (backend/data/cache) managed by the diskcache library; entries expire
    after CACHE_TTL_S seconds (6 hours by default).

"async" means these functions can wait for the network without blocking the
server: while one request waits on Google, others keep being served.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

import httpx
from diskcache import Cache

from ..config import get_settings

log = logging.getLogger(__name__)

# Identifies us politely to the websites we call (some APIs reject requests without one).
USER_AGENT = "MisInfoAI/2.0 (+https://github.com/pakson556/misinfo-ai)"

# Created on first use, then reused ("lazy" initialisation).
_client: httpx.AsyncClient | None = None
_cache: Cache | None = None


def client() -> httpx.AsyncClient:
    """The shared HTTP client (created the first time it's needed)."""
    global _client
    if _client is None or _client.is_closed:
        s = get_settings()
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(s.http_timeout_s),
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,  # follow "this page moved" responses automatically
            limits=httpx.Limits(max_connections=40, max_keepalive_connections=20),
        )
    return _client


def cache() -> Cache:
    """The on-disk cache, capped at 512 MB (oldest entries are removed first)."""
    global _cache
    if _cache is None:
        s = get_settings()
        path = s.data_dir / "cache"
        path.mkdir(parents=True, exist_ok=True)
        _cache = Cache(str(path), size_limit=512 * 1024 * 1024)
    return _cache


def cache_key(*parts: Any) -> str:
    """Turn a request (URL + parameters) into a fixed-length id, so identical requests share a cache entry."""
    raw = json.dumps(parts, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


async def get_json(
    url: str,
    *,
    params: dict | None = None,
    headers: dict | None = None,
    ttl: int | None = None,
) -> Any:
    """
    Fetch a URL and return its JSON, using the cache when possible.
    Network or HTTP errors are raised; retrieval.py catches them per source.
    """
    s = get_settings()
    key = cache_key("GET", url, params, sorted((headers or {}).items()))
    c = cache()
    hit = c.get(key)
    if hit is not None:
        return hit
    r = await client().get(url, params=params, headers=headers)
    r.raise_for_status()
    data = r.json()
    c.set(key, data, expire=ttl if ttl is not None else s.cache_ttl_s)
    return data


async def post_json(url: str, *, payload: dict, headers: dict | None = None, ttl: int | None = None) -> Any:
    """Same as get_json, for APIs that need a POST with a JSON body (e.g. Tavily)."""
    s = get_settings()
    key = cache_key("POST", url, payload)
    c = cache()
    hit = c.get(key)
    if hit is not None:
        return hit
    r = await client().post(url, json=payload, headers=headers)
    r.raise_for_status()
    data = r.json()
    c.set(key, data, expire=ttl if ttl is not None else s.cache_ttl_s)
    return data


async def aclose() -> None:
    """Close all open connections. Called once when the server shuts down."""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None

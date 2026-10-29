"""Shared async HTTP client with caching and polite defaults."""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

import httpx
from diskcache import Cache

from ..config import get_settings

log = logging.getLogger(__name__)

USER_AGENT = "MisInfoAI/2.0 (+https://github.com/pakson556/misinfo-ai)"

_client: httpx.AsyncClient | None = None
_cache: Cache | None = None


def client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        s = get_settings()
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(s.http_timeout_s),
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
            limits=httpx.Limits(max_connections=40, max_keepalive_connections=20),
        )
    return _client


def cache() -> Cache:
    global _cache
    if _cache is None:
        s = get_settings()
        path = s.data_dir / "cache"
        path.mkdir(parents=True, exist_ok=True)
        _cache = Cache(str(path), size_limit=512 * 1024 * 1024)
    return _cache


def cache_key(*parts: Any) -> str:
    raw = json.dumps(parts, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


async def get_json(
    url: str,
    *,
    params: dict | None = None,
    headers: dict | None = None,
    ttl: int | None = None,
) -> Any:
    """GET JSON with cache. Raises httpx errors to the caller."""
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
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None

"""Turn URLs and images into clean text."""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import shutil
import socket
from dataclasses import dataclass
from io import BytesIO
from urllib.parse import urlparse

from ..config import get_settings
from ..services import http

log = logging.getLogger(__name__)


class IngestError(ValueError):
    """A user-facing problem with the input."""


@dataclass
class Article:
    text: str
    title: str = ""
    url: str = ""
    published: str | None = None
    site: str = ""


# --------------------------------------------------------------------------- URL


def _assert_public_url(url: str) -> None:
    """Block requests to private/internal addresses (SSRF protection)."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise IngestError("Only public http(s) links can be analysed.")
    try:
        infos = socket.getaddrinfo(parsed.hostname, None)
    except socket.gaierror as e:
        raise IngestError("That link's website could not be found.") from e
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise IngestError("That link points to a private network address.")


async def fetch_article(url: str) -> Article:
    import trafilatura

    await asyncio.to_thread(_assert_public_url, url)
    try:
        r = await http.client().get(url)
        r.raise_for_status()
    except Exception as e:  # noqa: BLE001 - surface any network problem as user error
        raise IngestError(f"Could not open the link ({type(e).__name__}).") from e

    html = r.text
    extracted = await asyncio.to_thread(
        trafilatura.bare_extraction, html, url=str(r.url), include_comments=False, favor_precision=True
    )
    if not extracted:
        raise IngestError("Couldn't find readable article text at that link.")
    doc = extracted if isinstance(extracted, dict) else extracted.as_dict()
    text = (doc.get("text") or "").strip()
    if len(text) < 40:
        raise IngestError("The page has too little text to analyse.")
    s = get_settings()
    return Article(
        text=text[: s.max_input_chars],
        title=doc.get("title") or "",
        url=str(r.url),
        published=doc.get("date"),
        site=doc.get("sitename") or "",
    )


# --------------------------------------------------------------------------- OCR


def ocr_available() -> bool:
    try:
        import pytesseract  # noqa: F401
    except ImportError:
        return False
    return shutil.which("tesseract") is not None


def _ocr_sync(raw: bytes) -> str:
    import pytesseract
    from PIL import Image, ImageOps

    try:
        img = Image.open(BytesIO(raw))
        img.load()
    except Exception as e:  # noqa: BLE001
        raise IngestError("That file isn't a readable image.") from e

    img = ImageOps.exif_transpose(img).convert("L")
    w, h = img.size
    if w < 1400:  # upscale small screenshots; tesseract likes ~30px glyphs
        scale = 1400 / max(w, 1)
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    img = ImageOps.autocontrast(img)
    # Dark-mode screenshots: invert so text is dark on light
    if sum(img.resize((1, 1)).getdata()) < 110:
        img = ImageOps.invert(img)

    # psm 3 = automatic layout; better for multi-column social screenshots than psm 6
    text = pytesseract.image_to_string(img, config="--oem 3 --psm 3")
    lines = [ln.strip() for ln in text.splitlines()]
    # drop single-character noise lines common around UI icons
    cleaned = "\n".join(ln for ln in lines if len(ln) > 2)
    return cleaned.strip()


async def ocr_image(raw: bytes) -> str:
    if not ocr_available():
        raise IngestError("Image reading isn't installed on this server (needs Tesseract).")
    text = await asyncio.to_thread(_ocr_sync, raw)
    if len(text) < 10:
        raise IngestError("No readable text found in the image. Try a sharper screenshot.")
    return text

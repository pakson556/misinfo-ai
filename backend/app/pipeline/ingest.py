"""
Input handling: turns a link or a screenshot into plain text the pipeline can check.

LINKS  (fetch_article)
    1. Safety check: refuse links to private/internal addresses (see _assert_public_url).
    2. Download the page.
    3. trafilatura pulls out just the article text, leaving behind menus, ads and comments.

SCREENSHOTS  (ocr_image)
    OCR = Optical Character Recognition, reading text from an image.
    We use Tesseract, a free open-source OCR program. It's installed inside the
    Docker image; for local development install it yourself (brew install tesseract).
    The image is cleaned up first (greyscale, enlarged, contrast boosted, dark
    mode flipped) because Tesseract reads much better that way.

Problems the user can fix (bad link, blurry image, ...) raise IngestError with a
friendly message, which main.py returns to the website as a 422 error.
"""

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
    """What we extracted from a web page."""

    text: str
    title: str = ""
    url: str = ""
    published: str | None = None
    site: str = ""


# --------------------------------------------------------------------------- URL


def _assert_public_url(url: str) -> None:
    """
    Refuse links that point inside a private network (SSRF protection).

    Without this, someone could paste http://localhost:8000/... or a router's
    address (192.168.x.x) and make OUR server fetch things that should never be
    reachable from the internet. We look up the website's IP address and refuse
    private, loopback (127.0.0.1) and other reserved ranges.
    """
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise IngestError("Please use a normal web link that starts with http:// or https://.")
    try:
        infos = socket.getaddrinfo(parsed.hostname, None)
    except socket.gaierror as e:
        raise IngestError("We couldn't find that website. Check the link is typed correctly.") from e
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise IngestError("That link points to a private network, so we can't open it.")


async def fetch_article(url: str) -> Article:
    """Download a web page and extract its main article text."""
    import trafilatura  # imported here so the server starts faster when links aren't used

    # DNS lookups block, so run the safety check in a background thread.
    await asyncio.to_thread(_assert_public_url, url)
    try:
        r = await http.client().get(url)
        r.raise_for_status()
    except Exception as e:  # noqa: BLE001 - surface any network problem as user error
        raise IngestError("We couldn't open that link. The website may be down or blocking us.") from e

    html = r.text
    extracted = await asyncio.to_thread(
        trafilatura.bare_extraction, html, url=str(r.url), include_comments=False, favor_precision=True
    )
    if not extracted:
        raise IngestError("We couldn't find any article text at that link. Try copying and pasting the text instead.")
    doc = extracted if isinstance(extracted, dict) else extracted.as_dict()
    text = (doc.get("text") or "").strip()
    if len(text) < 40:
        raise IngestError("That page has too little text to check. Try copying and pasting the text instead.")
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
    """True if both the Python wrapper (pytesseract) and the tesseract program are installed."""
    try:
        import pytesseract  # noqa: F401
    except ImportError:
        return False
    return shutil.which("tesseract") is not None


def _ocr_sync(raw: bytes) -> str:
    """Clean up the image and read its text. Slow (CPU-heavy), so it's run in a thread by ocr_image()."""
    import pytesseract
    from PIL import Image, ImageOps

    try:
        img = Image.open(BytesIO(raw))
        img.load()
    except Exception as e:  # noqa: BLE001
        raise IngestError("That file isn't a picture we can open. Try a PNG or JPG screenshot.") from e

    # Rotate phone photos the right way up, then convert to greyscale ("L").
    img = ImageOps.exif_transpose(img).convert("L")
    w, h = img.size
    if w < 1400:  # upscale small screenshots; tesseract likes ~30px glyphs
        scale = 1400 / max(w, 1)
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    img = ImageOps.autocontrast(img)
    # Dark-mode screenshots: if the average pixel is dark, invert so text is dark on light.
    if sum(img.resize((1, 1)).getdata()) < 110:
        img = ImageOps.invert(img)

    # psm 3 = automatic layout; better for multi-column social screenshots than psm 6
    text = pytesseract.image_to_string(img, config="--oem 3 --psm 3")
    lines = [ln.strip() for ln in text.splitlines()]
    # drop single-character noise lines common around UI icons
    cleaned = "\n".join(ln for ln in lines if len(ln) > 2)
    return cleaned.strip()


async def ocr_image(raw: bytes) -> str:
    """Read the text in an uploaded image, or raise IngestError with a helpful message."""
    if not ocr_available():
        raise IngestError("Reading text from pictures isn't set up on this server yet.")
    text = await asyncio.to_thread(_ocr_sync, raw)
    if len(text) < 10:
        raise IngestError("We couldn't read any text in that picture. Try a clearer, larger screenshot.")
    return text

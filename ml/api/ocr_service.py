# ml/api/ocr_service.py
from __future__ import annotations

import os
from io import BytesIO
from typing import Optional, Tuple

# OCR is optional
try:
    import pytesseract
    from PIL import Image
    OCR_AVAILABLE = True
except ImportError:
    pytesseract = None
    Image = None
    OCR_AVAILABLE = False


def configure_tesseract() -> bool:
    """
    Configure the tesseract binary path (macOS Intel/ARM + Linux).
    Returns True if configured/found, False otherwise.
    """
    if not OCR_AVAILABLE:
        return False

    candidates = [
        "/opt/homebrew/bin/tesseract",  # macOS ARM (Apple Silicon)
        "/usr/local/bin/tesseract",     # macOS Intel
        "/usr/bin/tesseract",           # Linux
    ]

    for p in candidates:
        if os.path.exists(p):
            pytesseract.pytesseract.tesseract_cmd = p
            print(f"Tesseract configured: {p}")
            return True

    # fallback to PATH
    import shutil
    found = shutil.which("tesseract")
    if found:
        pytesseract.pytesseract.tesseract_cmd = found
        print(f"Tesseract found in PATH: {found}")
        return True

    print("⚠️ Tesseract not found. OCR endpoint will fail until installed.")
    return False


def extract_text_from_image_bytes(raw: bytes) -> str:
    """
    OCR -> text. Raises ValueError if OCR unavailable or extraction fails.
    """
    if not OCR_AVAILABLE or Image is None or pytesseract is None:
        raise ValueError("OCR not available. Install: pip install pytesseract pillow")

    img = Image.open(BytesIO(raw)).convert("RGB")
    extracted = (pytesseract.image_to_string(img) or "").strip()
    return extracted

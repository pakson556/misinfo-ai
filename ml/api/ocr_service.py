from __future__ import annotations

import os
import shutil
from io import BytesIO

# OCR is optional
try:
    import pytesseract
    from PIL import Image, ImageFilter, ImageOps
    OCR_AVAILABLE = True
except ImportError:
    pytesseract = None
    Image = None
    ImageFilter = None
    ImageOps = None
    OCR_AVAILABLE = False


def configure_tesseract() -> bool:
    """
    Configure the tesseract binary path (macOS Intel/ARM + Linux).
    Returns True if configured/found, False otherwise.
    """
    if not OCR_AVAILABLE or pytesseract is None:
        return False

    # If already configured and valid, keep it
    current_cmd = getattr(pytesseract.pytesseract, "tesseract_cmd", None)
    if current_cmd and os.path.exists(current_cmd):
        return True

    candidates = [
        "/opt/homebrew/bin/tesseract",  # macOS ARM (Apple Silicon)
        "/usr/local/bin/tesseract",     # macOS Intel
        "/usr/bin/tesseract",           # Linux
    ]

    for path in candidates:
        if os.path.exists(path):
            pytesseract.pytesseract.tesseract_cmd = path
            print(f"Tesseract configured: {path}")
            return True

    # fallback to PATH
    found = shutil.which("tesseract")
    if found:
        pytesseract.pytesseract.tesseract_cmd = found
        print(f"Tesseract found in PATH: {found}")
        return True

    print("Tesseract not found. OCR endpoint will fail until installed.")
    return False


def _preprocess_image(img: Image.Image) -> Image.Image:
    """
    Lightweight preprocessing to improve OCR accuracy.
    Keeps it simple so existing behaviour is not broken.
    """
    if ImageOps is None or ImageFilter is None:
        return img.convert("RGB")

    # Convert to grayscale
    img = ImageOps.grayscale(img)

    # Upscale small images to help OCR
    width, height = img.size
    if width < 1200:
        scale = max(1.5, 1200 / max(width, 1))
        img = img.resize((int(width * scale), int(height * scale)))

    # Improve contrast and sharpen slightly
    img = ImageOps.autocontrast(img)
    img = img.filter(ImageFilter.SHARPEN)

    return img


def extract_text_from_image_bytes(raw: bytes) -> str:
    """
    OCR -> text. Raises ValueError if OCR unavailable or extraction fails.
    """
    if not OCR_AVAILABLE or Image is None or pytesseract is None:
        raise ValueError("OCR not available. Install: pip install pytesseract pillow")

    if not configure_tesseract():
        raise ValueError(
            "OCR not available. Tesseract binary not found. "
            "Install Tesseract and ensure it is on PATH."
        )

    try:
        img = Image.open(BytesIO(raw))
        img = _preprocess_image(img)

        extracted = (
            pytesseract.image_to_string(
                img,
                config="--oem 3 --psm 6"
            )
            or ""
        ).strip()

        if not extracted:
            raise ValueError("No text could be extracted from the image.")

        return extracted

    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"OCR extraction failed: {exc}") from exc
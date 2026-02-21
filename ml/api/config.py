"""
API configuration: model paths, thresholds, CORS, and logging.
"""

from pathlib import Path

APP_VERSION = "2.1.0"

BASE_DIR = Path(__file__).parent.parent  # points to ml/
DATA_DIR = BASE_DIR / "data"
MODELS_DIR = DATA_DIR / "models"
LOGS_DIR = DATA_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

EVENTS_LOG = Path(__file__).parent / "data" / "logs" / "events.jsonl"

# CORS (frontend dev server)
ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

# Model files (trained by your training pipeline)
MODEL_UNIFIED = MODELS_DIR / "unified_binary_text_struct_logreg_calibrated.joblib"
MODEL_HEALTH = MODELS_DIR / "fakehealth_binary_text_logreg_calibrated.joblib"  # optional, may not exist
MODEL_EARLY = MODELS_DIR / "twitter15_16_binary_early_multimodal_k50_calibrated.joblib"  # optional

# Threshold JSON files (optional)
THRESHOLD_UNIFIED = MODELS_DIR / "unified_binary_text_struct_logreg_threshold.json"
THRESHOLD_HEALTH = MODELS_DIR / "fakehealth_binary_text_logreg_threshold.json"

DEFAULT_THRESHOLD_UNIFIED = 0.34
DEFAULT_THRESHOLD_HEALTH = 0.34

OCR_AVAILABLE = True

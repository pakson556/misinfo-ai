"""
API configuration: model paths, thresholds, CORS, logging, and defaults.
"""

from pathlib import Path

APP_VERSION = "2.2.0"

# File layout:
# ml/
#   api/
#     config.py
#   data/
#     models/
#     logs/
API_DIR = Path(__file__).resolve().parent
ML_DIR = API_DIR.parent
DATA_DIR = ML_DIR / "data"
MODELS_DIR = DATA_DIR / "models"
LOGS_DIR = DATA_DIR / "logs"

LOGS_DIR.mkdir(parents=True, exist_ok=True)

EVENTS_LOG = LOGS_DIR / "events.jsonl"

ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

# -----------------------------
# Model files
# -----------------------------
MODEL_UNIFIED = MODELS_DIR / "unified_binary_text_struct_logreg_calibrated.joblib"
MODEL_HEALTH = MODELS_DIR / "fakehealth_binary_text_logreg_calibrated.joblib"
MODEL_EARLY = MODELS_DIR / "twitter15_16_binary_early_multimodal_k50_calibrated.joblib"

ENHANCED_EARLY_MODEL = MODELS_DIR / "enhanced_early_multimodal_k50.joblib"
LEGACY_EARLY_MODEL = MODELS_DIR / "twitter15_16_binary_early_multimodal_k50_calibrated.joblib"

# -----------------------------
# Threshold files
# IMPORTANT:
# Use the threshold that matches the exact model filename.
# -----------------------------
THRESHOLD_UNIFIED = MODELS_DIR / "unified_binary_text_struct_logreg_calibrated_threshold.json"
THRESHOLD_HEALTH = MODELS_DIR / "fakehealth_binary_text_logreg_calibrated_threshold.json"

DEFAULT_THRESHOLD_UNIFIED = 0.34
DEFAULT_THRESHOLD_HEALTH = 0.34

# Internet verification defaults
ENABLE_INTERNET_VERIFICATION_DEFAULT = True
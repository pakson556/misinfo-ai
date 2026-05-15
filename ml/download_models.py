"""
Download trained model files from Hugging Face Hub.
Run this once after cloning the repo:

    python ml/download_models.py
"""

from pathlib import Path
from huggingface_hub import hf_hub_download

REPO_ID = "pakson/misinfo-ai-models"
MODELS_DIR = Path(__file__).parent / "data" / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

FILES = [
    "unified_binary_text_struct_logreg.joblib",
    "unified_binary_text_struct_logreg_calibrated.joblib",
    "unified_binary_text_struct_logreg_calibrated_threshold.json",
    "unified_binary_text_struct_logreg_threshold.json",
    "enhanced_early_multimodal_k50.joblib",
    "enhanced_early_multimodal_k50_threshold.json",
    "twitter15_16_binary_early_multimodal_k50.joblib",
    "twitter15_16_binary_early_multimodal_k50_calibrated.joblib",
    "twitter15_16_binary_early_multimodal_k50_calibrated_threshold.json",
    "calibration_summary.json",
    "training_summary.json",
]

for filename in FILES:
    dest = MODELS_DIR / filename
    if dest.exists():
        print(f"  already exists: {filename}")
        continue
    print(f"  downloading {filename}...")
    hf_hub_download(repo_id=REPO_ID, filename=filename, local_dir=MODELS_DIR)
    print(f"  ✓ {filename}")

print("\nAll models ready.")

"""
The optional machine-learning "style" model: the part that connects to your training work.

WHAT IT ANSWERS
    "Does this text *read* like the misinformation in our training datasets?"
    That's a narrower question than "is it true?". Style models are easy to fool
    and pick up quirks of their datasets, so this is a weak signal by design:
    aggregate.py gives it little weight, and the UI labels it clearly.

IS IT ON?
    Only if a trained model exists in backend/models/style/. With no model the
    app works normally and simply shows the style signal as unavailable.

HOW TO CREATE ONE (see training/README.md)
    training/baseline.py  -> TF-IDF + logistic regression, saved as model.joblib  (runs on a laptop)
    training/finetune.py  -> fine-tuned transformer, saved as model.onnx          (needs a GPU, e.g. Colab)

Expected files in STYLE_MODEL_DIR:
  meta.json                  {"type": "onnx"|"sklearn", "name": ..., "temperature": 1.0,
                              "max_length": 256, "metrics": {...}}
  model.onnx + tokenizer.json   (type "onnx": run with onnxruntime, no PyTorch needed)
  model.joblib                  (type "sklearn": a scikit-learn Pipeline that takes raw text)
"""

from __future__ import annotations

import json
import logging
import math
from functools import lru_cache
from pathlib import Path

from ..config import get_settings
from ..schemas import StyleSignal

log = logging.getLogger(__name__)


class _OnnxStyle:
    """Runs a fine-tuned transformer exported to ONNX (made by training/finetune.py)."""

    def __init__(self, d: Path, meta: dict):
        import numpy as np
        import onnxruntime as ort
        from tokenizers import Tokenizer

        self.np = np
        # The tokenizer splits text into the numbered word-pieces the model was trained on.
        self.max_length = int(meta.get("max_length", 256))
        self.temperature = float(meta.get("temperature", 1.0))
        self.tok = Tokenizer.from_file(str(d / "tokenizer.json"))
        self.tok.enable_truncation(self.max_length)
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 2  # don't hog every CPU core on a small server
        self.sess = ort.InferenceSession(str(d / "model.onnx"), opts, providers=["CPUExecutionProvider"])
        self.inputs = {i.name for i in self.sess.get_inputs()}

    def predict(self, text: str) -> float:
        """Probability (0..1) that the text reads like misinformation."""
        np = self.np
        enc = self.tok.encode(text)
        feed = {
            "input_ids": np.array([enc.ids], dtype=np.int64),
            "attention_mask": np.array([enc.attention_mask], dtype=np.int64),
        }
        if "token_type_ids" in self.inputs:
            feed["token_type_ids"] = np.array([enc.type_ids], dtype=np.int64)
        logits = self.sess.run(None, {k: v for k, v in feed.items() if k in self.inputs})[0][0]
        # The model outputs two scores ("logits") for [credible, misinformation].
        # Their difference, divided by the calibration temperature, goes through a
        # sigmoid to become a probability between 0 and 1.
        z = (float(logits[1]) - float(logits[0])) / self.temperature
        return 1 / (1 + math.exp(-z))


class _SklearnStyle:
    """Runs the TF-IDF baseline saved by training/baseline.py."""

    def __init__(self, d: Path, meta: dict):
        import joblib

        self.model = joblib.load(d / "model.joblib")

    def predict(self, text: str) -> float:
        return float(self.model.predict_proba([text])[0][1])


@lru_cache  # load the model once, the first time it's needed
def _load():
    """Load whichever model is in STYLE_MODEL_DIR. Returns (None, None) if there isn't one or it's broken."""
    d = get_settings().style_model_dir
    meta_path = d / "meta.json"
    if not meta_path.exists():
        return None, None
    meta = json.loads(meta_path.read_text())
    try:
        model = _OnnxStyle(d, meta) if meta.get("type") == "onnx" else _SklearnStyle(d, meta)
        log.info("Loaded style model %s", meta.get("name"))
        return model, meta
    except Exception:  # noqa: BLE001
        log.exception("Failed to load style model from %s", d)
        return None, None


def style_model_name() -> str | None:
    """Name of the installed model, or None. Shown in /api/health and the start-up log."""
    _, meta = _load()
    return meta.get("name") if meta else None


def style_signal(text: str) -> StyleSignal:
    """Score one text. Called by the orchestrator for every check."""
    model, meta = _load()
    if model is None:
        return StyleSignal(available=False, note="No style model installed. Train one with the scripts in /training.")
    p = model.predict(text[:5000])
    auc = (meta.get("metrics") or {}).get("cross_dataset_auc")
    note = (
        "Our AI compares how this is written with thousands of posts already known to be true or false. "
        "It only looks at the writing, not the facts."
    )
    # Reliability: 0 at AUC 0.5 (coin flip on unseen sources), 1 at AUC 0.8 or better.
    # A model that hasn't shown it generalises gets little say.
    reliability = 0.0
    if auc:
        note += (
            f" When tested on websites it had never seen, it scored {auc:.2f}"
            " (0.5 is no better than guessing, 1.0 is perfect), so it only has a small effect on the result."
        )
        reliability = max(0.0, min(1.0, (auc - 0.5) / 0.3))
    return StyleSignal(
        available=True, model=meta.get("name", ""), probability=round(p, 3), reliability=round(reliability, 2), note=note
    )

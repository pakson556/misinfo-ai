"""Optional writing-style classifier.

Answers a narrower question than the claim checker: "does this text *read* like
the misinformation in our training data?" It is a weak signal by design (style
models are easy to fool and pick up dataset quirks), so the aggregator gives it
little weight and the UI labels it clearly.

Expected layout of STYLE_MODEL_DIR (written by training/export.py):
  meta.json           {"type": "onnx"|"sklearn", "name": ..., "temperature": 1.0, "max_length": 256,
                       "metrics": {...}}
  model.onnx + tokenizer.json            (type onnx)
  model.joblib                           (type sklearn; a Pipeline taking raw text)
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
    def __init__(self, d: Path, meta: dict):
        import numpy as np
        import onnxruntime as ort
        from tokenizers import Tokenizer

        self.np = np
        self.max_length = int(meta.get("max_length", 256))
        self.temperature = float(meta.get("temperature", 1.0))
        self.tok = Tokenizer.from_file(str(d / "tokenizer.json"))
        self.tok.enable_truncation(self.max_length)
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 2
        self.sess = ort.InferenceSession(str(d / "model.onnx"), opts, providers=["CPUExecutionProvider"])
        self.inputs = {i.name for i in self.sess.get_inputs()}

    def predict(self, text: str) -> float:
        np = self.np
        enc = self.tok.encode(text)
        feed = {
            "input_ids": np.array([enc.ids], dtype=np.int64),
            "attention_mask": np.array([enc.attention_mask], dtype=np.int64),
        }
        if "token_type_ids" in self.inputs:
            feed["token_type_ids"] = np.array([enc.type_ids], dtype=np.int64)
        logits = self.sess.run(None, {k: v for k, v in feed.items() if k in self.inputs})[0][0]
        z = (float(logits[1]) - float(logits[0])) / self.temperature
        return 1 / (1 + math.exp(-z))


class _SklearnStyle:
    def __init__(self, d: Path, meta: dict):
        import joblib

        self.model = joblib.load(d / "model.joblib")

    def predict(self, text: str) -> float:
        return float(self.model.predict_proba([text])[0][1])


@lru_cache
def _load():
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
    _, meta = _load()
    return meta.get("name") if meta else None


def style_signal(text: str) -> StyleSignal:
    model, meta = _load()
    if model is None:
        return StyleSignal(available=False, note="No style model installed. Train one with the scripts in /training.")
    p = model.predict(text[:5000])
    auc = (meta.get("metrics") or {}).get("cross_dataset_auc")
    note = "Similarity to the writing style of misinformation in the training data. A weak signal: it doesn't check facts."
    if auc:
        note += f" Cross-dataset AUC: {auc:.2f}."
    return StyleSignal(available=True, model=meta.get("name", ""), probability=round(p, 3), note=note)

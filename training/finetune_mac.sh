#!/usr/bin/env bash
# Fine-tune the transformer style model on a Mac (Apple Silicon GPU is used automatically).
# Run from the project folder:   bash training/finetune_mac.sh
# Takes roughly 1-3 hours. Keep the Mac plugged in; "caffeinate" stops it sleeping.
set -euo pipefail
cd "$(dirname "$0")"

# 1. uv: a fast Python installer (gives us Python 3.12; the Mac's built-in 3.9 is too old)
if ! command -v uv >/dev/null 2>&1 && [ ! -x "$HOME/.local/bin/uv" ]; then
  echo ">> Installing uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi
export PATH="$HOME/.local/bin:$PATH"

# 2. A private Python environment for training (in training/.venv), with the packages
if [ ! -d .venv ]; then
  echo ">> Creating Python 3.12 environment..."
  uv venv --python 3.12 .venv
fi
echo ">> Installing packages (about 1-2 GB the first time)..."
uv pip install --python .venv/bin/python -q "torch>=2.5" "transformers>=4.46,<5" "datasets>=3.0" "accelerate>=1.0" \
  sentencepiece protobuf tiktoken "onnx>=1.16" "pandas>=2.2" "pyarrow>=16" "scikit-learn==1.9.1" joblib

# 3. Train. Output goes to backend/models/style_deberta (the current baseline is left alone).
echo ">> Training. Progress bars below; you can leave this running."
caffeinate -i .venv/bin/python finetune.py \
  --data data \
  --out ../backend/models/style_deberta \
  --epochs 2 --batch 8 --max-len 192 --eval-steps 1000

echo ""
echo ">> DONE. Results: backend/models/style_deberta/REPORT.md  - tell Claude it's finished."

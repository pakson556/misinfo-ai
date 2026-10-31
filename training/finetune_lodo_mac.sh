#!/usr/bin/env bash
# Leave-one-dataset-out test for the fine-tuned model (run AFTER finetune_mac.sh).
# Trains 6 short models, each without one dataset, and tests on the one left out.
# About 5-8 hours: start it before bed. Run from the project folder:
#   bash training/finetune_lodo_mac.sh
set -euo pipefail
cd "$(dirname "$0")"
export PATH="$HOME/.local/bin:$PATH"
caffeinate -i .venv/bin/python finetune.py --lodo-only \
  --data data \
  --out ../backend/models/style_deberta \
  --epochs 1 --batch 8 --max-len 128 --eval-steps 1000
echo ""
echo ">> DONE. Tell Claude the leave-one-out test has finished."

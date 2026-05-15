# MisInfo AI

An AI-powered misinformation detection platform built as a final year dissertation project. It analyses text and image-based content using an ensemble of machine learning models, BERT-based classification, and real-time internet verification.

> **Final Year Dissertation**
> Supervised by **Galvin Kaiyamo**

## Features

- **Text & Image Analysis** — paste text or upload a screenshot; the system runs OCR and scores content across three models
- **Ensemble Detection** — combines a rule-based classifier, BERT/transformer model, and a prediction service for higher accuracy
- **Internet Verification** — cross-references claims against the Google Fact Check Tools API and trusted fact-checking sources (Snopes, PolitiFact, FullFact, etc.)
- **Live Misinformation Feed** — real-time Google News RSS stream filtered for misinformation and debunking coverage
- **Explainability** — per-prediction explanations showing which signals drove the verdict
- **Dashboard & Global Monitor** — visualise trends, risk scores, and detection metrics over time

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React, Tailwind CSS, Lucide Icons |
| ML API | Python, FastAPI |
| Classification | BERT / DistilBERT (HuggingFace Transformers), rule-based fallback |
| Fact-checking | Google Fact Check Tools API |
| OCR | Tesseract / OCR service |

## Getting Started

### ML API

```bash
cd ml
pip install -r ../requirements.txt

# Download trained models from Hugging Face (one-time setup)
python download_models.py

uvicorn api.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Project Structure

```
misinfodetec/
├── frontend/          # React app
│   └── src/
│       ├── components/   # ResultCard, RiskActions, InternetVerificationPanel, ...
│       ├── pages/        # DetectionLab, GlobalMonitor, Dashboard
│       └── services/     # API client
└── ml/
    ├── api/              # FastAPI app — main.py, predict_service, bert_classifier, ...
    ├── training/         # Data prep and model training scripts
    └── data/             # Logs and model artefacts
```

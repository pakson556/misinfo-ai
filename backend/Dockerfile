FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1

# Tesseract powers screenshot reading
RUN apt-get update \
 && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt requirements-ml.txt ./
# Set WITH_ML=0 to skip onnxruntime/sklearn if you won't serve a style model
ARG WITH_ML=1
RUN pip install -r requirements.txt && if [ "$WITH_ML" = "1" ]; then pip install -r requirements-ml.txt; fi

COPY app ./app
# Optional trained style model (created by /training); folder may be empty
COPY models ./models

RUN useradd --create-home --uid 1000 app && mkdir -p /app/data && chown -R app /app/data
USER app

ENV DATA_DIR=/app/data
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s CMD curl -fsS http://localhost:8000/api/health || exit 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]

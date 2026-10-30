# =============================================================================
# Recipe for the BACKEND container (the Python API).
#
# A Dockerfile is a list of steps for building an "image": a snapshot of a
# tiny Linux computer with exactly the software this app needs. Docker runs
# that image as a "container". Because everything is inside, it works the same
# on your Mac, a friend's Windows PC, or a cloud server.
#
# Each instruction below adds a "layer". Docker caches layers, so if you only
# change your Python code, rebuilding skips the slow steps (installing packages).
# =============================================================================

# Start from an official image that already has Python 3.12 on a small Debian Linux.
FROM python:3.12-slim AS base

# Python settings: don't write .pyc files, print logs immediately, keep pip quiet and small.
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system programs: Tesseract (reads text from screenshots) and curl (used by the health check).
# Then delete apt's download cache to keep the image small.
RUN apt-get update \
 && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng curl \
 && rm -rf /var/lib/apt/lists/*

# All following commands run inside /app in the container.
WORKDIR /app

# Copy ONLY the requirements files first and install packages. Because the code
# is copied later, editing code doesn't invalidate this (slow) cached step.
COPY requirements.txt requirements-ml.txt ./
# Build with --build-arg WITH_ML=0 to skip the ML packages if you won't use a style model.
ARG WITH_ML=1
RUN pip install -r requirements.txt && if [ "$WITH_ML" = "1" ]; then pip install -r requirements-ml.txt; fi

# Now copy the application code.
COPY app ./app
# Optional trained style model (created by the scripts in /training); the folder may be empty.
COPY models ./models

# Security: run as a normal user, not "root" (administrator).
# /app/data is where the database and cache are written.
RUN useradd --create-home --uid 1000 app && mkdir -p /app/data && chown -R app /app/data
USER app

ENV DATA_DIR=/app/data
# The API listens on port 8000 inside the container.
EXPOSE 8000

# Every 30s Docker asks the API "are you OK?". docker-compose waits for this to
# pass before starting the frontend (that's the "Healthy" you saw in the log).
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s CMD curl -fsS http://localhost:8000/api/health || exit 1

# The command that starts the server when the container starts.
# --proxy-headers: trust the real visitor IP passed on by nginx (needed for rate limiting).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]

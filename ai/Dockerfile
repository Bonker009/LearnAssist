# syntax=docker/dockerfile:1
FROM python:3.12-slim

# ffmpeg        - audio extraction from media uploads (Phase 3)
# tesseract-ocr - fallback for scanned pages with no text layer (Phase 4).
#                 Chosen over PaddleOCR because paddlepaddle is a several-hundred-
#                 megabyte wheel, and OCR is a path most ingests never take.
#                 The Khmer pack reads photos of Khmer notes and scanned handouts.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg \
        tesseract-ocr \
        tesseract-ocr-eng \
        tesseract-ocr-khm \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /srv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/usr/local \
    PYTHONUNBUFFERED=1

# Dependency layer: cached unless pyproject.toml changes.
COPY pyproject.toml README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system -r pyproject.toml

COPY app ./app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--reload-dir", "/srv/app"]

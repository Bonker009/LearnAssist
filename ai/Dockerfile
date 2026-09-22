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
        sox \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /srv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/usr/local \
    PYTHONUNBUFFERED=1

# torch for Qwen3-ASR. The CPU index keeps the image small; build with
# --build-arg TORCH_INDEX_URL=https://download.pytorch.org/whl/cu128 for a GPU.
ARG TORCH_INDEX_URL=https://download.pytorch.org/whl/cpu
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system --index-url "$TORCH_INDEX_URL" "torch>=2.6"

# A CUDA torch ships cuBLAS and cuDNN as pip packages. Pointing the loader at them lets
# faster-whisper (CTranslate2) run on the GPU without a CUDA base image. The paths
# simply don't exist in a CPU build, which is harmless.
ENV LD_LIBRARY_PATH=/usr/local/lib/python3.12/site-packages/nvidia/cublas/lib:/usr/local/lib/python3.12/site-packages/nvidia/cudnn/lib

# Dependency layer: cached unless pyproject.toml changes.
COPY pyproject.toml README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system -r pyproject.toml

COPY app ./app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--reload-dir", "/srv/app"]

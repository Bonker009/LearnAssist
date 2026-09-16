"""FastAPI application entrypoint."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, status
from sqlalchemy import text

from app.config import get_settings
from app.db import dispose_engine, session_scope
from app.storage import ensure_bucket

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    try:
        await ensure_bucket()
    except Exception as exc:  # noqa: BLE001 - startup must not hard-fail on storage
        logger.warning("Could not ensure bucket at startup: %s", exc)
    yield
    await dispose_engine()


app = FastAPI(
    title="LearnAssist AI Service",
    description="Ingestion pipeline, RAG retrieval and quiz generation.",
    version="0.1.0",
    lifespan=lifespan,
)


async def require_internal_key(x_internal_key: str = Header(default="")) -> None:
    """Guard for endpoints Spring Boot calls.

    This service is not internet-facing and performs no ownership checks of its
    own — Spring Boot has already done that. This header only stops something
    else on the docker network from talking to it directly.
    """
    if x_internal_key != get_settings().internal_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="bad internal key")


@app.get("/health", tags=["ops"])
async def health() -> dict:
    """Liveness only — always cheap, never touches dependencies."""
    return {"status": "ok", "service": "ai"}


@app.get("/health/ready", tags=["ops"])
async def readiness() -> dict:
    """Readiness: reports each dependency separately so a failure is diagnosable.

    Ollama runs on the host, not in compose, so it is the one most likely to be
    missing on a fresh machine — it is reported distinctly rather than folded
    into a single boolean.
    """
    settings = get_settings()
    checks: dict[str, str] = {}

    try:
        async with session_scope() as session:
            await session.execute(text("SELECT 1"))
            result = await session.execute(
                text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
            )
            checks["postgres"] = "ok" if result.first() else "missing pgvector extension"
    except Exception as exc:  # noqa: BLE001
        checks["postgres"] = f"error: {exc}"

    try:
        await ensure_bucket()
        checks["rustfs"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["rustfs"] = f"error: {exc}"

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.ollama_base_url.rstrip('/')}/api/tags")
            response.raise_for_status()
            installed = {m["name"] for m in response.json().get("models", [])}
        missing = [
            model
            for model in (settings.ollama_chat_model, settings.ollama_embed_model)
            if model not in installed
        ]
        checks["ollama"] = "ok" if not missing else f"missing models: {', '.join(missing)}"
    except Exception as exc:  # noqa: BLE001
        checks["ollama"] = f"unreachable at {settings.ollama_base_url}: {exc}"

    ready = all(v == "ok" for v in checks.values())
    return {"ready": ready, "checks": checks}


@app.get("/internal/ping", tags=["ops"], dependencies=[Depends(require_internal_key)])
async def internal_ping() -> dict:
    return {"pong": True}

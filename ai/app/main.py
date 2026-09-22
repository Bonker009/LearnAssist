"""FastAPI application entrypoint."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    Form,
    Header,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from sqlalchemy import text

from app.config import get_settings
from app import cache
from app.db import dispose_engine, session_scope
from app.models import (
    FlashcardRequest,
    IngestRequest,
    QueryRequest,
    QueryResponse,
    QuizRequest,
    SlidesRequest,
    TranscriptResponse,
)
from app.quiz.generate import generate_quiz
from app.quiz.models import QuizQuestion
from app.rag.answer import answer_question
from app.rag.ingest import run_ingest
from app.transcribe.audio import FfmpegMissing
from app.transcribe.whisper import join_segments, transcribe_clip
from app.storage import ensure_bucket
from app.study.flashcards import Flashcard, generate_flashcards
from app.study.slides import SlideDeck, generate_slides

import contextvars

# Set per request from the X-Request-Id header Spring Boot forwards, so one user
# action is traceable across both services' logs.
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(request_id)s] %(name)s %(message)s",
)
for _handler in logging.getLogger().handlers:
    _handler.addFilter(RequestIdFilter())

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    try:
        await ensure_bucket()
    except Exception as exc:  # noqa: BLE001 - startup must not hard-fail on storage
        logger.warning("Could not ensure bucket at startup: %s", exc)
    yield
    await cache.close()
    await dispose_engine()


app = FastAPI(
    title="LearnAssist AI Service",
    description="Ingestion pipeline, RAG retrieval and quiz generation.",
    version="0.1.0",
    lifespan=lifespan,
)


@app.middleware("http")
async def bind_request_id(request: Request, call_next):
    incoming = request.headers.get("X-Request-Id", "")
    request_id_var.set(incoming[:64] if incoming else "-")
    response = await call_next(request)
    if incoming:
        response.headers["X-Request-Id"] = incoming[:64]
    return response


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

    # Redis is reported but never gates readiness: the cache is fail-open, so a
    # missing Redis makes answers slow, not unavailable.
    checks["redis"] = "ok" if await cache.ping() else "unavailable (answers will not be cached)"

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.ollama_base_url.rstrip('/')}/api/tags")
            response.raise_for_status()
            installed = {m["name"] for m in response.json().get("models", [])}
        missing = [
            model
            for model in (settings.ollama_chat_model, settings.ollama_embed_model)
            # Ollama lists an untagged pull as "name:latest".
            if model not in installed and f"{model}:latest" not in installed
        ]
        checks["ollama"] = "ok" if not missing else f"missing models: {', '.join(missing)}"
    except Exception as exc:  # noqa: BLE001
        checks["ollama"] = f"unreachable at {settings.ollama_base_url}: {exc}"

    required = ("postgres", "rustfs", "ollama")
    ready = all(checks[name] == "ok" for name in required)
    return {"ready": ready, "checks": checks}


@app.get("/internal/ping", tags=["ops"], dependencies=[Depends(require_internal_key)])
async def internal_ping() -> dict:
    return {"pong": True}


@app.post(
    "/ingest",
    status_code=status.HTTP_202_ACCEPTED,
    tags=["ingest"],
    dependencies=[Depends(require_internal_key)],
)
async def ingest(request: IngestRequest, background: BackgroundTasks) -> dict:
    """Queue ingestion and return immediately.

    Parsing, transcription and embedding take minutes, not milliseconds. The caller
    polls `ingest_jobs` for progress rather than holding a request open.
    """
    background.add_task(run_ingest, request)
    return {"queued": True, "documentId": str(request.document_id)}


@app.post("/query", tags=["rag"], dependencies=[Depends(require_internal_key)])
async def query(request: QueryRequest) -> QueryResponse:
    """Answer a question about one document.

    Ownership was already enforced by Spring Boot; this service scopes retrieval
    to the given document and nothing else.
    """
    return await answer_question(request)


@app.post("/quiz", tags=["quiz"], dependencies=[Depends(require_internal_key)])
async def quiz(request: QuizRequest) -> list[QuizQuestion]:
    """Generate practice questions for one document.

    Returns the correct answer and explanation; Spring Boot stores those and is
    responsible for never serialising them to the browser before submission.
    """
    questions = await generate_quiz(request.document_id, request.count)
    if not questions:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Could not generate questions from this document.",
        )
    return questions


@app.post("/flashcards", tags=["study"], dependencies=[Depends(require_internal_key)])
async def flashcards(request: FlashcardRequest) -> list[Flashcard]:
    """Generate revision flashcards for one document, each bound to its source."""
    cards = await generate_flashcards(request.document_id, request.count)
    if not cards:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Could not generate flashcards from this document.",
        )
    return cards


@app.post("/slides", tags=["study"], dependencies=[Depends(require_internal_key)])
async def slides(request: SlidesRequest) -> SlideDeck:
    """Generate a cited slide outline and the Slidev markdown rendered from it.

    Rendering the deck itself (build and PDF export) is the `slides` service's job;
    Spring Boot hands it the markdown returned here.
    """
    deck = await generate_slides(request.document_id, request.filename, request.count)
    if deck is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Could not generate slides from this document.",
        )
    return deck


# Dictation clips are seconds of Opus; this only bounds a malicious upload.
_MAX_CLIP_BYTES = 25 * 1024 * 1024
_CLIP_SUFFIXES = {
    "audio/webm": ".webm",
    "audio/ogg": ".ogg",
    "audio/mp4": ".m4a",
    "audio/mpeg": ".mp3",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
}


@app.post(
    "/transcribe",
    tags=["speech"],
    dependencies=[Depends(require_internal_key)],
    response_model=TranscriptResponse,
)
async def transcribe(
    file: UploadFile = File(...),
    language: str = Form("auto"),
) -> TranscriptResponse:
    """Transcribe a short voice message for the chat composer.

    Synchronous, unlike ingest: the student is waiting on the text, and a clip is
    seconds of audio, not an hour of lecture.
    """
    if language not in ("auto", "km", "en"):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "language must be auto, km or en")

    data = await file.read(_MAX_CLIP_BYTES + 1)
    if len(data) > _MAX_CLIP_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Recording is too large")
    if not data:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Recording is empty")

    content_type = (file.content_type or "").split(";")[0].strip().lower()
    suffix = _CLIP_SUFFIXES.get(content_type, ".webm")

    try:
        transcript = await transcribe_clip(data, suffix, None if language == "auto" else language)
    except FfmpegMissing as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    return TranscriptResponse(
        text=join_segments(transcript.segments, transcript.language),
        language=transcript.language,
        duration_sec=round(transcript.duration, 2),
    )

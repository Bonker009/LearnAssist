"""Ingestion pipeline: bytes -> units -> chunks -> vectors -> summary.

Ownership note. Spring Boot owns `documents`, `ingest_jobs` and `summaries` and is
the only service that creates or deletes those rows. This module makes a narrow,
deliberate exception: it UPDATES progress fields on rows Spring Boot already
created, and inserts the summary for a document it just processed. Routing every
progress tick back through an HTTP callback would add a second failure mode to the
one thing that has to stay reliable -- telling the student what is happening
during a slow ingest.
"""

import json
import logging
from uuid import UUID

from sqlalchemy import text

from app.chunking.splitter import chunk_units, count_tokens
from app.config import get_settings
from app.db import session_scope
from app.embeddings.ollama import get_embedding_provider
from app.llm.ollama import SummaryResult, get_llm_provider
from app.models import IngestRequest
from app.parsers.base import ParseResult
from app.parsers.pdf import PdfParser
from app.rag.prompts import SUMMARY_SYSTEM, build_summary_prompt
from app.rag.retrieve import delete_chunks, store_chunks
from app.storage import download_bytes

logger = logging.getLogger(__name__)

# Content type -> parser. Phases 2 and 3 register pptx/docx/audio/video here;
# nothing else in the pipeline changes.
_PARSERS = {"application/pdf": PdfParser}


async def _set_stage(document_id: UUID, stage: str, progress: int) -> None:
    async with session_scope() as session:
        await session.execute(
            text(
                "UPDATE ingest_jobs SET stage = :stage, progress = :progress, "
                "updated_at = now() WHERE document_id = :document_id"
            ),
            {"stage": stage, "progress": progress, "document_id": document_id},
        )


async def _fail(document_id: UUID, message: str) -> None:
    async with session_scope() as session:
        await session.execute(
            text(
                "UPDATE ingest_jobs SET stage = 'FAILED', error = :error, "
                "finished_at = now(), updated_at = now() WHERE document_id = :document_id"
            ),
            {"error": message[:2000], "document_id": document_id},
        )
        await session.execute(
            text("UPDATE documents SET status = 'FAILED', updated_at = now() WHERE id = :id"),
            {"id": document_id},
        )


def _select_parser(content_type: str):
    normalised = content_type.lower().split(";")[0].strip()
    parser = _PARSERS.get(normalised)
    if parser is None:
        raise ValueError(f"No parser registered for {content_type}")
    return parser()


async def _summarise(document_id: UUID, filename: str, result: ParseResult) -> None:
    settings = get_settings()
    llm = get_llm_provider()

    # Summarise from the start of the document within a token budget rather than
    # the whole thing: a 60-slide deck blows past a local model's context, and
    # the opening material is where the lecture states what it is about.
    collected: list[str] = []
    budget = settings.max_context_tokens
    for unit in result.units:
        cost = count_tokens(unit.text)
        if budget - cost < 0:
            break
        budget -= cost
        collected.append(unit.text)

    summary = await llm.complete_json(
        SUMMARY_SYSTEM,
        build_summary_prompt(filename, "\n\n".join(collected)),
        SummaryResult,
    )

    async with session_scope() as session:
        await session.execute(
            text(
                "INSERT INTO summaries (document_id, summary, key_concepts) "
                "VALUES (:document_id, :summary, CAST(:key_concepts AS jsonb)) "
                "ON CONFLICT (document_id) DO UPDATE "
                "SET summary = EXCLUDED.summary, key_concepts = EXCLUDED.key_concepts"
            ),
            {
                "document_id": document_id,
                "summary": summary.summary,
                "key_concepts": json.dumps([c.model_dump() for c in summary.key_concepts]),
            },
        )


async def run_ingest(request: IngestRequest) -> None:
    """Full pipeline for one document. Runs as a background task."""
    document_id = request.document_id
    try:
        await _set_stage(document_id, "PARSING", 5)
        data = await download_bytes(request.storage_key)

        parser = _select_parser(request.content_type)
        result = parser.parse(data)
        logger.info(
            "Parsed %s: %d units (%d need OCR)",
            request.filename, len(result.units), len(result.units_needing_ocr),
        )

        await _set_stage(document_id, "CHUNKING", 25)
        items = chunk_units(document_id, result.units)
        if not items:
            raise ValueError(
                "No readable text found. If this is a scanned PDF, OCR support is "
                "required to index it."
            )

        await _set_stage(document_id, "EMBEDDING", 40)
        embedder = get_embedding_provider()
        vectors = await embedder.embed_documents([c.embedding_text() for c in items])

        async with session_scope() as session:
            # Re-ingesting replaces the index rather than appending to it;
            # otherwise a retry silently doubles every chunk.
            await delete_chunks(session, document_id)
            await store_chunks(session, document_id, items, vectors)

        await _set_stage(document_id, "SUMMARIZING", 75)
        await _summarise(document_id, request.filename, result)

        async with session_scope() as session:
            await session.execute(
                text(
                    "UPDATE documents SET status = 'READY', unit_count = :unit_count, "
                    "duration_sec = :duration, updated_at = now() WHERE id = :id"
                ),
                {
                    "unit_count": result.unit_count,
                    "duration": result.duration_sec,
                    "id": document_id,
                },
            )
            await session.execute(
                text(
                    "UPDATE ingest_jobs SET stage = 'DONE', progress = 100, "
                    "finished_at = now(), updated_at = now() WHERE document_id = :id"
                ),
                {"id": document_id},
            )
        logger.info("Ingest complete for %s (%d chunks)", request.filename, len(items))

    except Exception as exc:  # noqa: BLE001 - background task must record every failure
        logger.exception("Ingest failed for document %s", document_id)
        await _fail(document_id, f"{type(exc).__name__}: {exc}")

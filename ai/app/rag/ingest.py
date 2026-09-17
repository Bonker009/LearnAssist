"""Ingestion pipeline: bytes -> units -> chunks -> vectors -> summary.

Ownership note. Spring Boot owns `documents`, `ingest_jobs` and `summaries` and is
the only service that creates or deletes those rows. This module makes a narrow,
deliberate exception: it UPDATES progress fields on rows Spring Boot already
created, and inserts the summary for a document it just processed. Routing every
progress tick back through an HTTP callback would add a second failure mode to the
one thing that has to stay reliable -- telling the student what is happening
during a slow ingest.
"""

import asyncio
import json
import logging
import pathlib
from collections.abc import Callable
from uuid import UUID

from sqlalchemy import text

from app import cache
from app.chunking.splitter import chunk_units, count_tokens
from app.config import get_settings
from app.db import session_scope
from app.embeddings.ollama import get_embedding_provider
from app.llm.ollama import SummaryResult, get_llm_provider
from app.models import IngestRequest
from app.ocr.render import render_pdf_page
from app.ocr.tesseract import get_ocr_provider
from app.models import SourceRef
from app.parsers.base import ParsedUnit, ParseResult
from app.parsers.docx import DocxParser
from app.parsers.pdf import PdfParser
from app.parsers.pptx import PptxParser
from app.parsers.text import TextParser
from app.parsers.web import WebParser
from app.fetch import fetch_public_page
from app.rag.prompts import SUMMARY_SYSTEM, build_summary_prompt
from app.rag.retrieve import delete_chunks, store_chunks
from app.storage import download_bytes, upload_bytes
from app.transcribe.whisper import WhisperTranscriber
from app.transcribe.youtube import download_audio

logger = logging.getLogger(__name__)

# Content type -> parser. Phases 2 and 3 register pptx/docx/audio/video here;
# nothing else in the pipeline changes.
_PARSERS = {
    "application/pdf": PdfParser,
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": PptxParser,
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": DocxParser,
    "text/plain": TextParser,
    "text/markdown": TextParser,
}


def reader_key(storage_key: str) -> str:
    """Key of the text snapshot for the in-app reader.

    Must match `StorageService.readerKey` in the API.
    """
    return f"{storage_key}.reader.json"


def build_reader_snapshot(result: ParseResult, source_url: str | None = None) -> bytes:
    """Serialise parsed units for the reader panel.

    Written from the units, not the chunks, because chunks overlap: rendering them
    back to back would repeat sentences at every split.
    """
    units = [
        {
            "kind": unit.source.kind,
            "page_no": unit.source.page_no,
            "slide_no": unit.source.slide_no,
            "label": unit.source.label(),
            "title": unit.section_title,
            "text": unit.text,
            "ocr": unit.ocr,
        }
        for unit in result.units
        if unit.text.strip()
    ]
    return json.dumps(
        {"version": 1, "source_url": source_url, "units": units}, ensure_ascii=False
    ).encode("utf-8")


def _normalised(content_type: str) -> str:
    return content_type.lower().split(";")[0].strip()


def _is_image(content_type: str) -> bool:
    return _normalised(content_type).startswith("image/")


def _image_result() -> ParseResult:
    """A photo is one unit whose only possible text is what OCR reads from it."""
    return ParseResult(
        units=[
            ParsedUnit(
                text="",
                source=SourceRef(kind="page", page_no=1, label_override="Image"),
                needs_ocr=True,
            )
        ],
        unit_count=1,
    )


async def _set_stage(document_id: UUID, stage: str, progress: int) -> None:
    async with session_scope() as session:
        await session.execute(
            text(
                "UPDATE ingest_jobs SET stage = :stage, progress = :progress, "
                "updated_at = now() WHERE document_id = :document_id"
            ),
            {"stage": stage, "progress": progress, "document_id": document_id},
        )


def _thread_safe_progress(
    loop: asyncio.AbstractEventLoop, document_id: UUID
) -> Callable[[float], None]:
    """Build a progress callback safe to call from Whisper's worker thread.

    Whisper runs in a thread (it is synchronous and CPU-bound), so there is no
    running loop there and `create_task` would raise. The loop is captured on the
    async side and the coroutine submitted across the boundary.

    Updates are throttled to whole percent changes: Whisper emits a segment every
    few seconds, and one UPDATE per segment would hammer Postgres for an hour with
    no visible benefit. A dropped update is harmless -- the next supersedes it.
    """
    last = -1

    def report(fraction: float) -> None:
        nonlocal last
        progress = 10 + int(min(max(fraction, 0.0), 1.0) * 50)
        if progress == last:
            return
        last = progress
        try:
            asyncio.run_coroutine_threadsafe(
                _set_stage(document_id, "TRANSCRIBING", progress), loop
            )
        except RuntimeError:
            pass  # loop closed: ingest is already finishing

    return report


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


async def _apply_ocr(
    document_id: UUID, result: ParseResult, render: Callable[[int], bytes | None]
) -> int:
    """Fill in units the parser flagged as scanned.

    `render` turns a unit's page number into image bytes: a rasterised PDF page, or
    for a photo upload, the photo itself.

    A page with no text layer would otherwise be silently absent from the index,
    which makes "the lecture does not cover this" a false statement rather than an
    honest one. Every recovered unit is marked `ocr=True` so the citation chip can
    tell the student the text was machine-read and may contain errors.

    @return the number of units recovered
    """
    pending = result.units_needing_ocr
    if not pending:
        return 0

    provider = get_ocr_provider()
    if not provider.available:
        logger.warning(
            "%d page(s) need OCR but tesseract is not installed; they stay unindexed",
            len(pending),
        )
        return 0

    await _set_stage(document_id, "OCR", 20)
    recovered = 0

    for index, unit in enumerate(pending):
        page_no = unit.source.page_no or unit.source.slide_no
        if page_no is None:
            continue

        image = await asyncio.to_thread(render, page_no)
        if image is None:
            continue

        # Tesseract is a blocking subprocess; a scanned 60-page deck would pin the
        # event loop for minutes if run inline.
        text = await asyncio.to_thread(provider.read, image)
        if text.strip():
            unit.text = text
            unit.ocr = True
            unit.needs_ocr = False
            recovered += 1

        if pending:
            await _set_stage(
                document_id, "OCR", 20 + int((index + 1) / len(pending) * 5)
            )

    logger.info("OCR recovered %d of %d unreadable page(s)", recovered, len(pending))
    return recovered


def _is_media(content_type: str) -> bool:
    return _normalised(content_type).startswith(("audio/", "video/"))


def _select_parser(content_type: str):
    parser = _PARSERS.get(_normalised(content_type))
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


async def _parse_youtube(request: IngestRequest) -> tuple[ParseResult, str | None]:
    audio = await download_audio(request.source_url or "")
    try:
        await _set_stage(request.document_id, "TRANSCRIBING", 10)
        result = await WhisperTranscriber().parse_file(
            audio.path,
            on_progress=_thread_safe_progress(asyncio.get_running_loop(), request.document_id),
        )
    finally:
        audio.cleanup()
    return result, audio.title


async def _parse_web(request: IngestRequest) -> tuple[ParseResult, str | None]:
    page = await fetch_public_page(request.source_url or "")
    if request.storage_key:
        # Keep what was actually read. The live page will change; the citation
        # should still be checkable against the version the answer came from.
        await upload_bytes(request.storage_key, page.content, page.content_type)
    parser = WebParser(page.final_url)
    result = parser.parse(page.content)
    return result, parser.title


async def run_ingest(request: IngestRequest) -> None:
    """Full pipeline for one document. Runs as a background task."""
    document_id = request.document_id
    filename = request.filename
    try:
        await _set_stage(document_id, "PARSING", 5)

        data: bytes | None = None
        title: str | None = None

        if request.doc_type == "YOUTUBE":
            # Transcription dominates the wall-clock time, so it reports real
            # progress across the 10-60% band.
            result, title = await _parse_youtube(request)
        elif request.doc_type == "WEB":
            result, title = await _parse_web(request)
        else:
            if not request.storage_key:
                raise ValueError("This resource has no uploaded file")
            data = await download_bytes(request.storage_key)

            if _is_media(request.content_type):
                await _set_stage(document_id, "TRANSCRIBING", 10)
                result = await WhisperTranscriber().parse(
                    data,
                    suffix=pathlib.Path(request.filename).suffix,
                    on_progress=_thread_safe_progress(
                        asyncio.get_running_loop(), document_id
                    ),
                )
            elif _is_image(request.content_type):
                result = _image_result()
            else:
                result = _select_parser(request.content_type).parse(data)

        logger.info(
            "Parsed %s: %d units (%d need OCR)",
            filename, len(result.units), len(result.units_needing_ocr),
        )

        # Scanned pages carry no text layer; recover them before chunking so they
        # are indexed like any other page.
        if data is not None and _is_image(request.content_type):
            image = data
            await _apply_ocr(document_id, result, lambda _page: image)
        elif data is not None and not _is_media(request.content_type):
            pdf = data
            await _apply_ocr(document_id, result, lambda page: render_pdf_page(pdf, page))

        if title:
            filename = title[:512]

        # Persist what parsing established before the slow stages run. Otherwise a
        # failure at embedding discards the page count and duration the UI needs to
        # describe the file at all.
        async with session_scope() as session:
            await session.execute(
                text(
                    "UPDATE documents SET unit_count = :unit_count, duration_sec = :duration, "
                    "filename = :filename, updated_at = now() WHERE id = :id"
                ),
                {
                    "unit_count": result.unit_count,
                    "duration": result.duration_sec,
                    "filename": filename,
                    "id": document_id,
                },
            )

        # Resources with no native browser viewer get a text snapshot, so a citation
        # to "Section 3" of a Word file or web page still opens on the cited text.
        # PDFs have the browser's viewer and media has a player; neither needs one.
        needs_reader = (
            request.storage_key
            and request.doc_type != "YOUTUBE"
            and not _is_media(request.content_type)
            and _normalised(request.content_type) != "application/pdf"
        )
        if needs_reader:
            await upload_bytes(
                reader_key(request.storage_key),
                build_reader_snapshot(result, request.source_url),
                "application/json",
            )

        await _set_stage(document_id, "CHUNKING", 25)
        items = chunk_units(document_id, result.units)
        if not items:
            unreadable = len(result.units_needing_ocr)
            if unreadable:
                raise ValueError(
                    f"No readable text found. {unreadable} page(s) appear to be scanned "
                    f"images and OCR could not read them."
                )
            raise ValueError("No readable text found in this file.")

        await _set_stage(document_id, "EMBEDDING", 40)
        embedder = get_embedding_provider()
        vectors = await embedder.embed_documents([c.embedding_text() for c in items])

        async with session_scope() as session:
            # Re-ingesting replaces the index rather than appending to it;
            # otherwise a retry silently doubles every chunk.
            await delete_chunks(session, document_id)
            await store_chunks(session, document_id, items, vectors)

        # Answers cached against the previous index cite chunks that no longer
        # exist; bumping the generation retires all of them at once.
        await cache.bump_generation(document_id)

        await _set_stage(document_id, "SUMMARIZING", 75)
        await _summarise(document_id, filename, result)

        async with session_scope() as session:
            await session.execute(
                text(
                    "UPDATE documents SET status = 'READY', updated_at = now() WHERE id = :id"
                ),
                {"id": document_id},
            )
            await session.execute(
                text(
                    "UPDATE ingest_jobs SET stage = 'DONE', progress = 100, "
                    "finished_at = now(), updated_at = now() WHERE document_id = :id"
                ),
                {"id": document_id},
            )
        logger.info("Ingest complete for %s (%d chunks)", filename, len(items))

    except Exception as exc:  # noqa: BLE001 - background task must record every failure
        logger.exception("Ingest failed for document %s", document_id)
        await _fail(document_id, f"{type(exc).__name__}: {exc}")

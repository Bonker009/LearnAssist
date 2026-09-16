"""Vector retrieval with neighbour expansion."""

import logging
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.chunking.splitter import count_tokens
from app.config import get_settings
from app.db import chunks as chunks_table
from app.embeddings.base import EmbeddingProvider
from app.models import Chunk, SourceRef

logger = logging.getLogger(__name__)


def _row_to_chunk(row) -> Chunk:
    return Chunk(
        document_id=row.document_id,
        ordinal=row.ordinal,
        text=row.text,
        section_title=row.section_title,
        ocr=row.ocr,
        source=SourceRef(
            kind=row.source_kind,
            label_override=row.source_label,
            slide_no=row.slide_no,
            page_no=row.page_no,
            start_sec=row.start_sec,
            end_sec=row.end_sec,
        ),
    )


async def store_chunks(
    session: AsyncSession, document_id: UUID, items: list[Chunk],
    embeddings: list[list[float]]
) -> None:
    if len(items) != len(embeddings):
        raise ValueError("chunk/embedding count mismatch")

    rows = [
        {
            "id": uuid4(),
            "document_id": document_id,
            "ordinal": chunk.ordinal,
            "text": chunk.text,
            "section_title": chunk.section_title,
            "source_kind": chunk.source.kind,
            "source_label": chunk.source.label_override,
            "slide_no": chunk.source.slide_no,
            "page_no": chunk.source.page_no,
            "start_sec": chunk.source.start_sec,
            "end_sec": chunk.source.end_sec,
            "ocr": chunk.ocr,
            "embedding": embedding,
        }
        for chunk, embedding in zip(items, embeddings, strict=True)
    ]
    if rows:
        await session.execute(chunks_table.insert(), rows)


async def delete_chunks(session: AsyncSession, document_id: UUID) -> None:
    """Clear a document's chunks so a re-ingest does not double-index it."""
    await session.execute(
        chunks_table.delete().where(chunks_table.c.document_id == document_id)
    )


async def retrieve(
    session: AsyncSession,
    document_id: UUID,
    question: str,
    embedder: EmbeddingProvider,
) -> list[Chunk]:
    """Find the chunks most likely to answer `question`, with context.

    Scoped to a single document throughout: a student asking about one lecture
    must never be answered from another, and restricting the search also keeps
    recall high on a small corpus.
    """
    settings = get_settings()
    query_vector = await embedder.embed_query(question)

    distance = chunks_table.c.embedding.cosine_distance(query_vector)
    hits = (
        await session.execute(
            select(chunks_table, distance.label("distance"))
            .where(chunks_table.c.document_id == document_id)
            .order_by(distance)
            .limit(settings.retrieval_top_k)
        )
    ).all()

    if not hits:
        return []

    # Expand each hit to its neighbours: a definition and the sentence that uses
    # it usually land in adjacent chunks, and retrieving one without the other
    # produces a technically-sourced but useless answer.
    wanted: set[int] = set()
    for row in hits:
        for offset in range(-settings.neighbour_window, settings.neighbour_window + 1):
            if row.ordinal + offset >= 0:
                wanted.add(row.ordinal + offset)

    expanded = (
        await session.execute(
            select(chunks_table)
            .where(
                chunks_table.c.document_id == document_id,
                chunks_table.c.ordinal.in_(wanted),
            )
            .order_by(chunks_table.c.ordinal)
        )
    ).all()

    by_ordinal = {row.ordinal: _row_to_chunk(row) for row in expanded}

    # Keep relevance order (best hit first) so that if the context budget forces
    # a truncation, it is the least relevant material that is dropped.
    ordered: list[Chunk] = []
    seen: set[int] = set()
    for row in hits:
        for offset in range(-settings.neighbour_window, settings.neighbour_window + 1):
            ordinal = row.ordinal + offset
            if ordinal in by_ordinal and ordinal not in seen:
                seen.add(ordinal)
                ordered.append(by_ordinal[ordinal])

    budget = settings.max_context_tokens
    selected: list[Chunk] = []
    for chunk in ordered:
        cost = count_tokens(chunk.text)
        if budget - cost < 0:
            break
        budget -= cost
        selected.append(chunk)

    logger.debug(
        "Retrieved %d hits -> %d chunks after expansion and budgeting",
        len(hits), len(selected),
    )
    return selected

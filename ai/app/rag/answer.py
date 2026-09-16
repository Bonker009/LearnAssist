"""Question answering over one document's chunks."""

import logging

from app.db import session_scope
from app.embeddings.ollama import get_embedding_provider
from app.llm.ollama import get_llm_provider
from app.models import QueryRequest, QueryResponse
from app.rag.citations import NOT_COVERED, is_grounded, resolve_citations
from app.rag.prompts import QA_SYSTEM, build_qa_prompt
from app.rag.retrieve import retrieve

logger = logging.getLogger(__name__)


async def answer_question(request: QueryRequest) -> QueryResponse:
    embedder = get_embedding_provider()

    async with session_scope() as session:
        chunks = await retrieve(session, request.document_id, request.question, embedder)

    if not chunks:
        # No chunks at all means nothing was indexed; answering anyway would
        # produce pure invention.
        return QueryResponse(answer=NOT_COVERED, citations=[], grounded=False)

    # Markers are 1-based to match how the prompt renders them.
    blocks = {index: chunk for index, chunk in enumerate(chunks, start=1)}
    rendered = [
        (marker, chunk.source.label(), chunk.text) for marker, chunk in blocks.items()
    ]

    llm = get_llm_provider()
    raw = await llm.complete(QA_SYSTEM, build_qa_prompt(request.question, rendered))

    answer, citations = resolve_citations(raw, blocks)
    grounded = is_grounded(answer, citations)

    if not grounded and NOT_COVERED.lower() not in answer.lower():
        # The model produced prose with no surviving citation. Rather than show an
        # unsupported claim that looks authoritative, fall back to the refusal.
        logger.info("Ungrounded answer discarded for document %s", request.document_id)
        return QueryResponse(answer=NOT_COVERED, citations=[], grounded=False)

    return QueryResponse(answer=answer, citations=citations, grounded=grounded)

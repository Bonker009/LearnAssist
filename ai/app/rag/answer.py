"""Question answering over the resources attached to one chat."""

import logging

from app import cache, guard
from app.db import session_scope
from app.embeddings.ollama import get_embedding_provider
from app.lang import detect_language
from app.llm.ollama import get_llm_provider
from app.models import QueryRequest, QueryResponse, Turn
from app.rag.citations import is_grounded, not_covered_message, resolve_citations
from app.rag.prompts import QA_SYSTEM, build_qa_prompt
from app.rag.retrieve import retrieve

logger = logging.getLogger(__name__)


def retrieval_query(question: str, history: list[Turn]) -> str:
    """The text embedded for retrieval.

    A follow-up like "and what about the second stage?" has almost nothing to embed on
    its own. Prepending the previous question carries the topic forward without an
    extra model call to rewrite the question, which would add tens of seconds on a
    local model to every turn.
    """
    previous = next((t.content for t in reversed(history) if t.role == "USER"), None)
    return f"{previous}\n{question}" if previous else question


async def answer_question(request: QueryRequest) -> QueryResponse:
    language = detect_language(request.question)
    document_ids = request.document_ids

    # Guardrail on the way in: before the cache, retrieval or the model see it.
    verdict = await guard.check_question(request.question)
    if not verdict.allowed:
        logger.warning("Question blocked by guard (%s)", ", ".join(verdict.flagged))
        return QueryResponse(
            answer=guard.blocked_question_message(language), citations=[], grounded=False
        )

    # Only a chat's first question is cacheable: with history, the same words can
    # mean something different ("explain that again").
    cacheable = not request.history
    if cacheable:
        cached = await cache.get_answer(document_ids, request.question)
        if cached is not None:
            return QueryResponse.model_validate(cached)

    embedder = get_embedding_provider()
    async with session_scope() as session:
        chunks = await retrieve(
            session, document_ids, retrieval_query(request.question, request.history), embedder
        )

    if not chunks:
        # No chunks at all means nothing was indexed; answering anyway would
        # produce pure invention.
        return QueryResponse(answer=not_covered_message(language), citations=[], grounded=False)

    # With several resources attached, "Page 4" is ambiguous to the model too; naming
    # the file lets it say which one it drew on.
    filenames = {d.id: d.filename for d in request.documents}
    several = len({chunk.document_id for chunk in chunks}) > 1

    # Markers are 1-based to match how the prompt renders them.
    blocks = {index: chunk for index, chunk in enumerate(chunks, start=1)}
    rendered = [
        (
            marker,
            f"{filenames.get(chunk.document_id, 'file')} · {chunk.source.label()}"
            if several
            else chunk.source.label(),
            chunk.text,
        )
        for marker, chunk in blocks.items()
    ]
    history = [(turn.role, turn.content) for turn in request.history]

    llm = get_llm_provider()
    raw = await llm.complete(
        QA_SYSTEM, build_qa_prompt(request.question, rendered, history, language)
    )

    answer, citations = resolve_citations(raw, blocks)
    if not is_grounded(answer, citations):
        # Either the model refused, or it produced prose with no surviving citation.
        # Both become the localised refusal: an unsupported claim that looks
        # authoritative is worse than an honest "not covered".
        logger.info("Ungrounded answer for documents %s", document_ids)
        return QueryResponse(answer=not_covered_message(language), citations=[], grounded=False)

    # Guardrail on the way out, before the answer is cached or shown.
    verdict = await guard.check_answer(request.question, answer)
    if not verdict.allowed:
        logger.warning("Answer blocked by guard (%s)", ", ".join(verdict.flagged))
        return QueryResponse(
            answer=guard.blocked_answer_message(language), citations=[], grounded=False
        )

    response = QueryResponse(answer=answer, citations=citations, grounded=True)
    # Only grounded answers are cached. A refusal is often the result of a transient
    # retrieval miss, and caching it would make a temporary failure permanent.
    if cacheable:
        await cache.set_answer(document_ids, request.question, response.model_dump())
    return response

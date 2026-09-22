"""Quiz generation."""

import logging
from uuid import UUID

from sqlalchemy import select

from app.db import chunks as chunks_table
from app.db import session_scope
from app.llm.ollama import get_llm_provider
from app.quiz.models import GeneratedQuestion, GeneratedQuiz, QuizQuestion
from app.quiz.prompts import QUIZ_SYSTEM, build_quiz_prompt
from app.quiz.sampling import stratified_sample
from app.models import Chunk
from app.rag.citations import snippet as make_snippet
from app.rag.retrieve import _row_to_chunk

logger = logging.getLogger(__name__)

# Sample more blocks than questions asked for, so the model has room to skip a
# block it cannot build a fair question from.
SAMPLE_MULTIPLIER = 2


async def load_document_chunks(document_id: UUID) -> list[Chunk]:
    """Every chunk of one document, in reading order.

    Shared by the quiz, flashcard and slide generators, which all sample from the
    whole document rather than from a retrieval query.
    """
    async with session_scope() as session:
        rows = (
            await session.execute(
                select(chunks_table)
                .where(chunks_table.c.document_id == document_id)
                .order_by(chunks_table.c.ordinal)
            )
        ).all()
    return [_row_to_chunk(row) for row in rows]


async def generate_quiz(document_id: UUID, count: int = 5) -> list[QuizQuestion]:
    chunks = await load_document_chunks(document_id)
    if not chunks:
        return []

    sampled = stratified_sample(chunks, count * SAMPLE_MULTIPLIER)

    blocks = {marker: chunk for marker, chunk in enumerate(sampled, start=1)}
    rendered = [(m, c.source.label(), c.text) for m, c in blocks.items()]

    llm = get_llm_provider()
    generated = await llm.complete_json(
        QUIZ_SYSTEM,
        build_quiz_prompt(rendered, count),
        GeneratedQuiz,
        # A little variety, but not so much that the model drifts off the source.
        temperature=0.4,
    )

    questions = _validate(generated.questions, blocks)

    if len(questions) < count:
        logger.info(
            "Only %d of %d questions survived validation; regenerating once",
            len(questions), count,
        )
        retry = await llm.complete_json(
            QUIZ_SYSTEM,
            build_quiz_prompt(rendered, count - len(questions)),
            GeneratedQuiz,
            temperature=0.5,
        )
        questions.extend(_validate(retry.questions, blocks))

    return questions[:count]


def _validate(
    generated: list[GeneratedQuestion], blocks: dict[int, Chunk]
) -> list[QuizQuestion]:
    """Keep only questions that are answerable and genuinely sourced.

    Pydantic has already enforced four distinct options and an in-range answer.
    What remains is the thing the model gets wrong most often: citing a block that
    was never provided. Such a question cannot be shown in review mode -- there is
    nothing to show -- so it is dropped rather than displayed without a source.
    """
    kept: list[QuizQuestion] = []

    for question in generated:
        chunk = blocks.get(question.source_marker)
        if chunk is None:
            logger.debug(
                "Dropping question citing unknown block %d", question.source_marker
            )
            continue

        kept.append(
            QuizQuestion(
                question=question.question.strip(),
                options=question.options,
                correct_index=question.correct_index,
                explanation=question.explanation.strip(),
                source=chunk.source,
                source_label=chunk.source.label(),
                snippet=make_snippet(chunk.text),
            )
        )

    return kept

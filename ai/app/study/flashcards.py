"""Flashcard generation."""

import logging
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from app.llm.ollama import get_llm_provider
from app.models import Chunk, SourceRef
from app.quiz.generate import load_document_chunks
from app.quiz.sampling import stratified_sample
from app.rag.citations import snippet as make_snippet

logger = logging.getLogger(__name__)

# As with quizzes: offer more blocks than cards so the model can skip thin ones.
SAMPLE_MULTIPLIER = 2

FLASHCARD_SYSTEM = """You write revision flashcards from lecture material.

Return JSON: {"cards": [...]}, where each card is:
  {"front": "...", "back": "...", "source_marker": 1}

Rules:
1. Use ONLY what the numbered blocks actually say. Never add outside knowledge.
2. The front is a short prompt: a term to define, or a direct question.
3. The back answers it in one to three sentences a student can check themselves on.
4. One idea per card. Do not repeat a card.
5. "source_marker" must be the number of the block the card came from.
6. Cover as many different blocks as possible.
7. Write each card in the language of the block it came from."""


def build_flashcard_prompt(blocks: list[tuple[int, str, str]], count: int) -> str:
    rendered = "\n\n".join(f"[{marker}] ({label})\n{text}" for marker, label, text in blocks)
    return f"""Lecture material:

{rendered}

---
Write {count} flashcards. Return only the JSON object."""


class GeneratedCard(BaseModel):
    """One card exactly as the model returned it, before validation."""

    front: str = Field(min_length=2, max_length=300)
    back: str = Field(min_length=1, max_length=800)
    source_marker: int


class GeneratedDeck(BaseModel):
    cards: list[GeneratedCard]


class Flashcard(BaseModel):
    """A validated card bound to its source. camelCase for Jackson, like `QuizQuestion`."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    front: str
    back: str
    source: SourceRef
    source_label: str
    snippet: str


def validate_cards(generated: list[GeneratedCard], blocks: dict[int, Chunk]) -> list[Flashcard]:
    """Drop cards that cite an unknown block, and repeats of a front already kept."""
    kept: list[Flashcard] = []
    seen: set[str] = set()
    for card in generated:
        chunk = blocks.get(card.source_marker)
        front = " ".join(card.front.split())
        key = front.casefold()
        if chunk is None or key in seen:
            continue
        seen.add(key)
        kept.append(
            Flashcard(
                front=front,
                back=" ".join(card.back.split()),
                source=chunk.source,
                source_label=chunk.source.label(),
                snippet=make_snippet(chunk.text),
            )
        )
    return kept


async def generate_flashcards(document_id: UUID, count: int = 10) -> list[Flashcard]:
    chunks = await load_document_chunks(document_id)
    if not chunks:
        return []

    sampled = stratified_sample(chunks, count * SAMPLE_MULTIPLIER)
    blocks = dict(enumerate(sampled, start=1))
    rendered = [(m, c.source.label(), c.text) for m, c in blocks.items()]

    llm = get_llm_provider()
    generated = await llm.complete_json(
        FLASHCARD_SYSTEM, build_flashcard_prompt(rendered, count), GeneratedDeck, temperature=0.4
    )
    cards = validate_cards(generated.cards, blocks)

    if len(cards) < count:
        logger.info("Only %d of %d cards survived validation; regenerating once", len(cards), count)
        retry = await llm.complete_json(
            FLASHCARD_SYSTEM,
            build_flashcard_prompt(rendered, count - len(cards)),
            GeneratedDeck,
            temperature=0.5,
        )
        cards = validate_cards(generated.cards + retry.cards, blocks)

    return cards[:count]

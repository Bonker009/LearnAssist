"""Turn parsed units into embeddable chunks.

The governing rule: a chunk NEVER spans two source references. A chunk drawn from
both slide 3 and slide 4 cannot be cited unambiguously, and an ambiguous citation
defeats the entire purpose of the product. Splitting therefore happens strictly
*within* one unit, and two short units are never merged.
"""

import re
from uuid import UUID

import tiktoken

from app.config import get_settings
from app.models import Chunk
from app.parsers.base import ParsedUnit

# cl100k_base is a reasonable proxy for any modern tokenizer's counts; this is
# used for budgeting, not for actually tokenising model input.
_encoding = tiktoken.get_encoding("cl100k_base")

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def count_tokens(text: str) -> int:
    return len(_encoding.encode(text))


def _split_long_text(text: str, max_tokens: int, overlap_tokens: int) -> list[str]:
    """Split one unit's text on sentence boundaries, with overlap.

    Overlap matters because a definition is often split from the term it defines;
    without it the second half retrieves as a context-free fragment.
    """
    if count_tokens(text) <= max_tokens:
        return [text]

    sentences = [s for s in _SENTENCE_END.split(text) if s.strip()]
    parts: list[str] = []
    current: list[str] = []
    current_tokens = 0

    for sentence in sentences:
        sentence_tokens = count_tokens(sentence)

        # A single sentence longer than the budget (common in bad OCR output or a
        # slide with no punctuation) has no boundary to split on; hard-split it
        # rather than emitting an oversized chunk.
        if sentence_tokens > max_tokens:
            if current:
                parts.append(" ".join(current))
                current, current_tokens = [], 0
            words = sentence.split()
            buffer: list[str] = []
            for word in words:
                buffer.append(word)
                if count_tokens(" ".join(buffer)) >= max_tokens:
                    parts.append(" ".join(buffer))
                    buffer = []
            if buffer:
                current, current_tokens = [" ".join(buffer)], count_tokens(" ".join(buffer))
            continue

        if current_tokens + sentence_tokens > max_tokens and current:
            parts.append(" ".join(current))
            # Carry the tail of the previous part forward as overlap.
            carry: list[str] = []
            carry_tokens = 0
            for previous in reversed(current):
                previous_tokens = count_tokens(previous)
                if carry_tokens + previous_tokens > overlap_tokens:
                    break
                carry.insert(0, previous)
                carry_tokens += previous_tokens
            current, current_tokens = carry, carry_tokens

        current.append(sentence)
        current_tokens += sentence_tokens

    if current:
        parts.append(" ".join(current))
    return [p for p in parts if p.strip()]


def chunk_units(document_id: UUID, units: list[ParsedUnit]) -> list[Chunk]:
    """Flatten parsed units into ordered chunks.

    `ordinal` is assigned across the whole document so retrieval can expand a hit
    to its neighbours (`ordinal +/- 1`) regardless of which unit they came from.
    """
    settings = get_settings()
    chunks: list[Chunk] = []
    ordinal = 0

    for unit in units:
        text = unit.text.strip()
        if not text:
            # An empty unit (a blank slide, or a scanned page before OCR runs)
            # contributes no retrievable content and is skipped rather than
            # embedded as an empty vector.
            continue

        for part in _split_long_text(text, settings.max_chunk_tokens,
                                     settings.chunk_overlap_tokens):
            chunks.append(
                Chunk(
                    document_id=document_id,
                    ordinal=ordinal,
                    text=part,
                    source=unit.source,
                    section_title=unit.section_title,
                    ocr=unit.ocr,
                )
            )
            ordinal += 1

    return chunks

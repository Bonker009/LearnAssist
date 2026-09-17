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

# Latin punctuation needs following whitespace (so "3.5" and "e.g." survive). The
# Khmer khan ។ and bariyoosan ៕ are unambiguous and are often written with no space
# after them, so they split with or without one.
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+|(?<=[។៕])\s*")


def count_tokens(text: str) -> int:
    return len(_encoding.encode(text))


def _hard_split_word(word: str, max_tokens: int) -> list[str]:
    """Cut a single space-free run into pieces under the token budget.

    Cuts land before a base character, never before a combining mark, so a Khmer
    consonant is not separated from its vowel sign or subscript.
    """
    if count_tokens(word) <= max_tokens:
        return [word]

    import unicodedata

    # Khmer tokenises at several tokens per character; estimate the step from this
    # word's own ratio and leave headroom rather than binary-searching every piece.
    step = max(1, int(len(word) * max_tokens / count_tokens(word) * 0.9))
    pieces: list[str] = []
    start = 0
    while start < len(word):
        end = min(start + step, len(word))
        while end < len(word) and end > start + 1 and (
            unicodedata.category(word[end]).startswith("M") or word[end - 1] == "្"
        ):
            end -= 1
        pieces.append(word[start:end])
        start = end
    return pieces


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
            # Khmer writes words without spaces, so one "word" here can be a whole
            # paragraph; cut those by characters rather than emit them oversized.
            words = [piece for word in sentence.split()
                     for piece in _hard_split_word(word, max_tokens)]
            buffer: list[str] = []
            for word in words:
                # Flush before adding a word that would overflow, not after: with
                # near-budget pieces, flushing after appending emits two of them
                # together at twice the budget.
                if buffer and count_tokens(" ".join([*buffer, word])) > max_tokens:
                    parts.append(" ".join(buffer))
                    buffer = []
                buffer.append(word)
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

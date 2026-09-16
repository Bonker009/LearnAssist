"""Chunking must never produce an ambiguous citation."""

from uuid import uuid4

from app.chunking.splitter import chunk_units, count_tokens
from app.config import get_settings
from app.models import SourceRef
from app.parsers.base import ParsedUnit


def _units():
    return [
        ParsedUnit(text="Slide one content about mitosis.",
                   source=SourceRef(kind="slide", slide_no=1), section_title="Mitosis"),
        ParsedUnit(text="Slide two content about meiosis.",
                   source=SourceRef(kind="slide", slide_no=2), section_title="Meiosis"),
    ]


def test_short_units_are_never_merged():
    """Two adjacent short slides must stay separate.

    Merging them would produce one chunk citable as either slide -- exactly the
    ambiguity the whole design exists to prevent.
    """
    chunks = chunk_units(uuid4(), _units())
    assert len(chunks) == 2
    assert chunks[0].source.slide_no == 1
    assert chunks[1].source.slide_no == 2


def test_ordinals_are_contiguous_and_ordered():
    chunks = chunk_units(uuid4(), _units())
    assert [c.ordinal for c in chunks] == list(range(len(chunks)))


def test_long_unit_splits_but_keeps_one_source():
    settings = get_settings()
    long_text = " ".join(
        f"Sentence number {i} explains an important detail of the topic." for i in range(400)
    )
    unit = ParsedUnit(text=long_text, source=SourceRef(kind="page", page_no=7),
                      section_title="Long Page")
    chunks = chunk_units(uuid4(), [unit])

    assert len(chunks) > 1, "a very long page should split"
    # Every resulting chunk still points at exactly page 7.
    assert {c.source.page_no for c in chunks} == {7}
    assert {c.source.kind for c in chunks} == {"page"}


def test_chunks_respect_the_token_budget():
    settings = get_settings()
    long_text = " ".join(
        f"Sentence number {i} explains an important detail of the topic." for i in range(400)
    )
    unit = ParsedUnit(text=long_text, source=SourceRef(kind="page", page_no=1))
    for chunk in chunk_units(uuid4(), [unit]):
        # Allow modest slack: splitting happens on sentence boundaries, so the
        # last sentence can push a chunk slightly over budget.
        assert count_tokens(chunk.text) <= settings.max_chunk_tokens * 1.3


def test_empty_units_are_skipped():
    units = [
        ParsedUnit(text="   ", source=SourceRef(kind="page", page_no=1)),
        ParsedUnit(text="Real content.", source=SourceRef(kind="page", page_no=2)),
    ]
    chunks = chunk_units(uuid4(), units)
    assert len(chunks) == 1
    assert chunks[0].source.page_no == 2


def test_section_title_is_prepended_for_embedding_only():
    chunks = chunk_units(uuid4(), _units())
    chunk = chunks[0]
    assert chunk.embedding_text().startswith("Mitosis")
    # The stored text stays clean; the title is not duplicated into it.
    assert not chunk.text.startswith("Mitosis")

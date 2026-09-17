"""Chat interface: multi-resource answers, text and web resources, Khmer handling."""

import json
from uuid import uuid4

import pytest

from app.chunking.splitter import chunk_units, count_tokens
from app.lang import detect_language
from app.models import Chunk, QueryRequest, SourceRef, Turn
from app.parsers.base import ParsedUnit
from app.parsers.text import decode_text, parse_text
from app.rag.answer import retrieval_query
from app.rag.citations import (
    NOT_COVERED,
    is_grounded,
    not_covered_message,
    resolve_citations,
)
from app.rag.prompts import build_qa_prompt
from app.transcribe.windows import Segment, group_segments
from app.transcribe.whisper import join_segments

# ---------- language ----------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("What does RuBisCO do?", "other"),
        ("តើរស្មីសំយោគជាអ្វី?", "km"),
        # A Khmer question about an English term is still a Khmer question.
        ("RuBisCO ធ្វើអ្វីខ្លះ?", "km"),
        ("Qu'est-ce que la photosynthèse ?", "other"),
        ("123 ?", "other"),
    ],
)
def test_detect_language(text, expected):
    assert detect_language(text) == expected


# ---------- citations across several resources ----------


def test_citation_carries_its_document():
    """With two files attached, "Page 1" alone would not say which one to open."""
    lecture, notes = uuid4(), uuid4()
    blocks = {
        1: Chunk(document_id=lecture, ordinal=0, text="Chloroplasts.",
                 source=SourceRef(kind="page", page_no=1)),
        2: Chunk(document_id=notes, ordinal=0, text="Calvin cycle.",
                 source=SourceRef(kind="page", page_no=1, label_override="Paragraph 1")),
    }
    _, citations = resolve_citations("A [1] and B [2].", blocks)
    assert [c.document_id for c in citations] == [lecture, notes]


def test_refusal_sentinel_is_ungrounded_and_localised():
    assert is_grounded(NOT_COVERED, []) is False
    assert "ឯកសារ" in not_covered_message("km")
    assert not_covered_message("other") != NOT_COVERED


# ---------- request contract ----------


def test_query_request_accepts_the_java_payload():
    """Jackson sends camelCase; a mismatch here surfaces as a 422 at runtime."""
    doc = uuid4()
    request = QueryRequest.model_validate(
        {
            "documents": [{"id": str(doc), "filename": "lecture.pdf"}],
            "question": "Why?",
            "history": [{"role": "USER", "content": "What is X?"}],
        }
    )
    assert request.document_ids == [doc]
    assert request.history[0].role == "USER"


def test_query_request_needs_a_resource():
    with pytest.raises(ValueError):
        QueryRequest.model_validate({"documents": [], "question": "Why?"})


# ---------- follow-ups ----------


def test_follow_up_retrieval_carries_the_previous_question():
    history = [
        Turn(role="USER", content="What is the Calvin cycle?"),
        Turn(role="ASSISTANT", content="It fixes carbon [1]."),
    ]
    query = retrieval_query("And where does it happen?", history)
    assert "Calvin cycle" in query
    assert query.endswith("And where does it happen?")


def test_first_question_is_embedded_as_is():
    assert retrieval_query("What is ATP?", []) == "What is ATP?"


def test_history_markers_are_stripped_from_the_prompt():
    """An old [1] names a block from a previous retrieval; it must not be copyable."""
    prompt = build_qa_prompt(
        "And then?",
        [(1, "Page 2", "Fresh context.")],
        [("USER", "What is X?"), ("ASSISTANT", "X is Y [7].")],
        "other",
    )
    assert "[7]" not in prompt
    assert "Assistant: X is Y." in prompt
    assert "[1] (Page 2)" in prompt


def test_khmer_question_asks_for_a_khmer_answer():
    prompt = build_qa_prompt("តើវាជាអ្វី?", [(1, "Page 1", "text")], None, "km")
    assert "Khmer" in prompt


# ---------- text resources ----------


def test_markdown_splits_at_headings():
    result = parse_text("Intro line.\n\n# Light reactions\nMake ATP.\n\n## Calvin cycle\nFix CO2.")
    labels = [u.source.label() for u in result.units]
    assert labels == ["Section 1", "Section 2", "Section 3"]
    assert result.units[1].section_title == "Light reactions"
    assert "Fix CO2." in result.units[2].text


def test_plain_notes_are_grouped_by_paragraph():
    paragraphs = [f"Paragraph {i} " + "word " * 100 for i in range(1, 9)]
    result = parse_text("\n\n".join(paragraphs))
    assert len(result.units) > 1
    assert result.units[0].source.label().startswith("Paragraph")
    # page_no is the running index the reader scrolls to.
    assert [u.source.page_no for u in result.units] == list(range(1, len(result.units) + 1))
    # No paragraph lost or duplicated across groups.
    joined = "\n\n".join(u.text for u in result.units)
    assert all(p.strip() in joined for p in paragraphs)
    assert joined.count("Paragraph 1 ") == 1


def test_decode_handles_bom_and_utf16():
    assert decode_text("﻿សួស្តី".encode("utf-8")) == "សួស្តី"
    assert decode_text("notes".encode("utf-16")) == "notes"


# ---------- web resources ----------


def test_web_parser_keeps_the_article_and_drops_navigation():
    pytest.importorskip("trafilatura")
    from app.parsers.web import WebParser

    body = " ".join(["Photosynthesis converts light energy into chemical energy."] * 12)
    html = f"""<html><head><title>Photosynthesis &amp; you</title></head><body>
      <nav><a href="/">Home</a> <a href="/shop">Shop our merchandise</a></nav>
      <article><h1>Photosynthesis</h1><p>{body}</p>
      <h2>The Calvin cycle</h2><p>{body.replace('Photosynthesis', 'The Calvin cycle')}</p>
      </article>
      <footer>Copyright 2026 Example Corp. Shop our merchandise.</footer></body></html>"""

    parser = WebParser("https://example.com/photosynthesis")
    result = parser.parse(html.encode())
    text = " ".join(u.text for u in result.units)
    assert parser.title == "Photosynthesis & you"
    assert "light energy" in text
    assert "merchandise" not in text


def test_web_parser_rejects_a_page_with_no_article():
    pytest.importorskip("trafilatura")
    from app.parsers.web import WebParser

    with pytest.raises(ValueError, match="readable"):
        WebParser().parse(b"<html><body><div id='app'></div><script>x()</script></body></html>")


# ---------- Khmer text ----------

_KHMER_SENTENCE = "រស្មីសំយោគបំប្លែងថាមពលពន្លឺទៅជាថាមពលគីមីនៅក្នុងក្លរ៉ូប្លាស្ទ។"


def test_khmer_long_unit_splits_on_khan():
    text = _KHMER_SENTENCE * 400
    unit = ParsedUnit(text=text, source=SourceRef(kind="page", page_no=1))
    chunks = chunk_units(uuid4(), [unit])
    assert len(chunks) > 1
    assert all(c.text.endswith("។") for c in chunks[:-1])


def test_khmer_without_punctuation_is_cut_but_never_mid_cluster():
    """No spaces and no khan: the character fallback must still respect clusters."""
    from app.config import get_settings

    text = _KHMER_SENTENCE.rstrip("។") * 300
    unit = ParsedUnit(text=text, source=SourceRef(kind="page", page_no=1))
    chunks = chunk_units(uuid4(), [unit])
    limit = get_settings().max_chunk_tokens

    assert len(chunks) > 1
    import unicodedata

    for chunk in chunks:
        assert count_tokens(chunk.text) <= limit * 1.1
        for piece in chunk.text.split(" "):
            assert not unicodedata.category(piece[0]).startswith("M"), "piece starts with a mark"
            assert piece[-1] != "្", "piece ends with a dangling coeng"


def test_khmer_khan_closes_a_transcript_window():
    segments = [
        Segment(start=i * 5.0, end=(i + 1) * 5.0, text=_KHMER_SENTENCE) for i in range(20)
    ]
    units = group_segments(segments)
    assert len(units) > 1


def test_khmer_dictation_segments_join_without_spaces():
    segments = [Segment(0, 1, " សួស្តី"), Segment(1, 2, "បងស្រី ")]
    assert join_segments(segments, "km") == "សួស្តីបងស្រី"
    assert join_segments([Segment(0, 1, " hello"), Segment(1, 2, "there ")], "en") == "hello there"


# ---------- reader snapshot ----------


def test_reader_snapshot_uses_units_not_overlapping_chunks():
    from app.parsers.base import ParseResult
    from app.rag.ingest import build_reader_snapshot, reader_key

    result = ParseResult(
        units=[
            ParsedUnit(text="First.", source=SourceRef(kind="page", page_no=1,
                                                       label_override="Section 1"),
                       section_title="Intro"),
            ParsedUnit(text="   ", source=SourceRef(kind="page", page_no=2)),
            ParsedUnit(text="ខ្មែរ", source=SourceRef(kind="slide", slide_no=3)),
        ]
    )
    snapshot = json.loads(build_reader_snapshot(result, "https://example.com"))
    assert [u["label"] for u in snapshot["units"]] == ["Section 1", "Slide 3"]
    assert snapshot["units"][1]["text"] == "ខ្មែរ"
    assert snapshot["source_url"] == "https://example.com"
    assert reader_key("u/2026/x.docx") == "u/2026/x.docx.reader.json"

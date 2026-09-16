"""Citation resolution is the product's integrity guarantee, so it is tested hard."""

from uuid import uuid4

from app.models import Chunk, SourceRef
from app.rag.citations import NOT_COVERED, is_grounded, resolve_citations


def _blocks():
    doc = uuid4()
    return {
        1: Chunk(document_id=doc, ordinal=0, text="Photosynthesis happens in chloroplasts.",
                 source=SourceRef(kind="page", page_no=1)),
        2: Chunk(document_id=doc, ordinal=1, text="The Calvin cycle fixes carbon dioxide.",
                 source=SourceRef(kind="slide", slide_no=4)),
        3: Chunk(document_id=doc, ordinal=2, text="Transcribed narration about RuBisCO.",
                 source=SourceRef(kind="timestamp", start_sec=750.0, end_sec=795.0)),
    }


def test_valid_markers_resolve_to_their_sources():
    answer, citations = resolve_citations(
        "Photosynthesis occurs in chloroplasts [1] and fixes carbon [2].", _blocks())
    assert len(citations) == 2
    assert citations[0].label == "Page 1"
    assert citations[1].label == "Slide 4"
    assert "[1]" in answer and "[2]" in answer


def test_fabricated_marker_is_stripped():
    """A model citing a block it was never given must not reach the UI.

    Rendering a chip for [9] would imply the claim was checked against the
    lecture when nothing supports it -- worse than showing no citation at all.
    """
    answer, citations = resolve_citations(
        "Photosynthesis occurs in chloroplasts [1]. Mitochondria make ATP [9].", _blocks())
    assert [c.marker for c in citations] == [1]
    assert "[9]" not in answer
    # Stripping must not leave a gap before the full stop.
    assert " ." not in answer
    assert "Mitochondria make ATP." in answer


def test_answer_of_only_fabricated_markers_has_no_citations():
    answer, citations = resolve_citations("Entirely invented claim [7][8].", _blocks())
    assert citations == []
    assert "[7]" not in answer and "[8]" not in answer


def test_timestamp_label_is_minutes_and_seconds():
    _, citations = resolve_citations("As explained in the recording [3].", _blocks())
    assert citations[0].label == "12:30"


def test_repeated_marker_is_reported_once():
    _, citations = resolve_citations("First [1]. Second [1]. Third [1].", _blocks())
    assert len(citations) == 1


def test_refusal_is_not_grounded():
    assert is_grounded(NOT_COVERED, []) is False


def test_prose_without_citations_is_not_grounded():
    assert is_grounded("Some confident but unsourced claim.", []) is False


def test_cited_answer_is_grounded():
    _, citations = resolve_citations("Chloroplasts [1].", _blocks())
    assert is_grounded("Chloroplasts [1].", citations) is True

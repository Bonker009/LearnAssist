"""Quiz validation and sampling.

Everything the model returns is untrusted. A malformed question that reaches a
student is worse than a missing one: it is unanswerable, and it undermines trust
in the questions that are fine.
"""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.models import Chunk, SourceRef
from app.quiz.generate import _validate
from app.quiz.models import GeneratedQuestion
from app.quiz.sampling import stratified_sample

DOC = uuid4()


def _question(**overrides):
    base = {
        "question": "Where does photosynthesis occur?",
        "options": ["Chloroplast", "Nucleus", "Ribosome", "Golgi body"],
        "correct_index": 0,
        "explanation": "The slide states it occurs in the chloroplast.",
        "source_marker": 1,
    }
    base.update(overrides)
    return base


def _chunks(count: int, text_len: int = 200) -> list[Chunk]:
    return [
        Chunk(
            document_id=DOC,
            ordinal=i,
            text=f"Chunk {i} " + ("content " * (text_len // 8)),
            source=SourceRef(kind="slide", slide_no=i + 1),
        )
        for i in range(count)
    ]


# ---------- shape validation ----------


def test_valid_question_is_accepted():
    assert GeneratedQuestion(**_question()).correct_index == 0


@pytest.mark.parametrize("options", [
    ["A", "B", "C"],
    ["A", "B", "C", "D", "E"],
    ["A", "B", "C", ""],
])
def test_wrong_option_count_is_rejected(options):
    with pytest.raises(ValidationError):
        GeneratedQuestion(**_question(options=options))


def test_duplicate_options_are_rejected():
    """Two identical choices make the question unanswerable."""
    with pytest.raises(ValidationError):
        GeneratedQuestion(**_question(options=["Mitosis", "Meiosis", "Mitosis", "Binary fission"]))


def test_case_insensitive_duplicates_are_rejected():
    with pytest.raises(ValidationError):
        GeneratedQuestion(**_question(options=["Mitosis", "mitosis", "Meiosis", "Cytokinesis"]))


@pytest.mark.parametrize("index", [-1, 4, 99])
def test_out_of_range_answer_is_rejected(index):
    """An answer index past the end of the list cannot be graded at all."""
    with pytest.raises(ValidationError):
        GeneratedQuestion(**_question(correct_index=index))


def test_last_valid_index_is_accepted():
    assert GeneratedQuestion(**_question(correct_index=3)).correct_index == 3


# ---------- source binding ----------


def test_question_citing_an_unknown_block_is_dropped():
    """The model's most common error: citing a block it was never given.

    Such a question has nothing to show in review mode, so it is dropped rather
    than displayed with a source the student cannot check.
    """
    blocks = {1: _chunks(1)[0]}
    kept = _validate([GeneratedQuestion(**_question(source_marker=7))], blocks)
    assert kept == []


def test_valid_question_keeps_its_source():
    chunks = _chunks(2)
    blocks = {1: chunks[0], 2: chunks[1]}
    kept = _validate([GeneratedQuestion(**_question(source_marker=2))], blocks)
    assert len(kept) == 1
    assert kept[0].source.slide_no == 2
    assert kept[0].source_label == "Slide 2"
    assert kept[0].snippet


def test_mixed_batch_keeps_only_the_sound_questions():
    chunks = _chunks(1)
    blocks = {1: chunks[0]}
    kept = _validate(
        [
            GeneratedQuestion(**_question(source_marker=1)),
            GeneratedQuestion(**_question(source_marker=99)),
            GeneratedQuestion(**_question(source_marker=1, question="Second good one?")),
        ],
        blocks,
    )
    assert len(kept) == 2


# ---------- sampling ----------


def test_sampling_spreads_across_the_document():
    """Questions must not all come from the start of the lecture.

    A similarity search against a generic query concentrates everything on the
    opening slides, which is useless for revision.
    """
    selected = stratified_sample(_chunks(60), 6)
    ordinals = sorted(c.ordinal for c in selected)
    assert len(selected) == 6
    assert ordinals[0] < 10, "should draw from the beginning"
    assert ordinals[-1] > 45, "should draw from the end"


def test_sampling_returns_distinct_chunks():
    selected = stratified_sample(_chunks(40), 8)
    assert len({c.ordinal for c in selected}) == len(selected)


def test_sampling_with_fewer_chunks_than_requested():
    selected = stratified_sample(_chunks(3), 10)
    assert len(selected) == 3


def test_sampling_of_empty_document():
    assert stratified_sample([], 5) == []


def test_sampling_prefers_substantial_chunks():
    """A two-line chunk rarely holds enough to build a fair question from."""
    chunks = [
        Chunk(document_id=DOC, ordinal=0, text="Short.",
              source=SourceRef(kind="page", page_no=1)),
        Chunk(document_id=DOC, ordinal=1, text="A much longer chunk " * 30,
              source=SourceRef(kind="page", page_no=2)),
    ]
    selected = stratified_sample(chunks, 1)
    assert selected[0].ordinal == 1

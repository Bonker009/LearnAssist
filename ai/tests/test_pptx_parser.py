"""Slide attribution, speaker notes and table text."""

import pathlib

import pytest

from app.parsers.pptx import PptxParser

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "lecture_sample.pptx"


@pytest.fixture(scope="module")
def parsed():
    return PptxParser().parse(FIXTURE.read_bytes())


def test_slide_count(parsed):
    assert parsed.unit_count == 4
    assert len(parsed.units) == 4


def test_every_unit_is_a_slide_reference(parsed):
    for index, unit in enumerate(parsed.units, start=1):
        assert unit.source.kind == "slide"
        assert unit.source.slide_no == index
        assert unit.source.page_no is None
        assert unit.source.start_sec is None


def test_titles_become_section_titles(parsed):
    assert parsed.units[0].section_title == "Cell Structure"
    assert parsed.units[1].section_title == "The Mitochondrion"


@pytest.mark.parametrize(
    ("phrase", "expected_slide"),
    [
        ("basic unit of life", 1),
        ("double membrane", 2),
        ("identical daughter cells", 3),
    ],
)
def test_phrase_resolves_to_the_right_slide(parsed, phrase, expected_slide):
    matches = [u.source.slide_no for u in parsed.units if phrase.lower() in u.text.lower()]
    assert expected_slide in matches


def test_speaker_notes_are_captured(parsed):
    """Notes usually hold the real explanation; losing them loses the best content."""
    assert "ribosomes" in parsed.units[0].text.lower()
    assert "cristae" in parsed.units[1].text.lower()


def test_notes_are_attributed_to_their_own_slide(parsed):
    # The cristae note belongs to slide 2 and must not bleed into slide 1.
    assert "cristae" not in parsed.units[0].text.lower()


def test_table_text_is_captured(parsed):
    table_slide = parsed.units[3]
    assert "Prokaryote" in table_slide.text
    assert "Absent" in table_slide.text


def test_title_is_not_duplicated_into_body(parsed):
    assert parsed.units[0].text.count("Cell Structure") == 0

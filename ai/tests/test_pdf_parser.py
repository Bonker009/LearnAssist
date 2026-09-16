"""The parser must map known text to the exact page a student can turn to."""

import pathlib

import pytest

from app.parsers.pdf import PdfParser

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "lecture_sample.pdf"


@pytest.fixture(scope="module")
def parsed():
    return PdfParser().parse(FIXTURE.read_bytes())


def test_page_count(parsed):
    assert parsed.unit_count == 3
    assert len(parsed.units) == 3


def test_every_unit_is_a_page_reference(parsed):
    for index, unit in enumerate(parsed.units, start=1):
        assert unit.source.kind == "page"
        assert unit.source.page_no == index
        # A page-addressed chunk must not carry slide or timestamp coordinates.
        assert unit.source.slide_no is None
        assert unit.source.start_sec is None


@pytest.mark.parametrize(
    ("phrase", "expected_page"),
    [
        ("chloroplasts", 1),
        ("thylakoid membrane", 2),
        ("RuBisCO", 3),
        ("Calvin cycle", 3),
    ],
)
def test_phrase_resolves_to_the_right_page(parsed, phrase, expected_page):
    """This is the citation guarantee, tested at its source."""
    matches = [u.source.page_no for u in parsed.units if phrase.lower() in u.text.lower()]
    assert expected_page in matches, f"{phrase!r} not found on page {expected_page}"


def test_headings_are_extracted(parsed):
    titles = [u.section_title for u in parsed.units]
    assert titles[0] is not None
    assert "Photosynthesis" in titles[0]


def test_text_pdf_is_not_flagged_as_scanned(parsed):
    assert not parsed.units_needing_ocr

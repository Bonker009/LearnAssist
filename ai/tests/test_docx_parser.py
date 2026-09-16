"""Word sections, reading order and honest labelling."""

import pathlib

import pytest

from app.parsers.docx import DocxParser

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "lecture_sample.docx"


@pytest.fixture(scope="module")
def parsed():
    return DocxParser().parse(FIXTURE.read_bytes())


def test_splits_at_headings(parsed):
    titles = [u.section_title for u in parsed.units]
    assert "Mendelian Inheritance" in titles
    assert "Molecular Genetics" in titles


def test_sections_are_indexed_in_order(parsed):
    numbers = [u.source.page_no for u in parsed.units]
    assert numbers == sorted(numbers)
    assert numbers[0] == 1


def test_label_says_section_not_page(parsed):
    """Word has no page concept a parser can see.

    Rendering "Page 3" would assert something the file does not contain; the unit
    is a heading section, so that is what the citation says.
    """
    for unit in parsed.units:
        assert unit.source.label() == f"Section {unit.source.page_no}"
        assert "Page" not in unit.source.label()


def test_kind_stays_page_for_uniform_retrieval(parsed):
    # The storage/retrieval path has no Word special case; only the label differs.
    assert {u.source.kind for u in parsed.units} == {"page"}


@pytest.mark.parametrize(
    ("phrase", "expected_title"),
    [
        ("dominant and recessive", "Mendelian Inheritance"),
        ("DNA polymerase", "Molecular Genetics"),
    ],
)
def test_phrase_lands_in_the_right_section(parsed, phrase, expected_title):
    matches = [u.section_title for u in parsed.units if phrase.lower() in u.text.lower()]
    assert expected_title in matches


def test_table_text_is_captured_in_document_order(parsed):
    """A table must appear where it actually sits, not appended at the end.

    python-docx exposes paragraphs and tables as separate sequences; reading them
    one after the other would scramble the reading order.
    """
    combined = "\n".join(u.text for u in parsed.units)
    assert "Masked by dominant" in combined
    last_section = parsed.units[-1]
    assert "Recessive" in last_section.text

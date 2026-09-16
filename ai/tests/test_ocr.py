"""OCR fallback for pages with no text layer.

A scanned page that stays unindexed does not merely lose content -- it makes the
system's honest refusal ("the lecture does not cover this") into a false
statement, because the lecture does cover it.
"""

import pathlib
import shutil

import pytest

from app.ocr.render import render_pdf_page
from app.ocr.tesseract import TesseractOcrProvider
from app.parsers.pdf import PdfParser

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
SCANNED = FIXTURES / "lecture_scanned.pdf"
TEXT_PDF = FIXTURES / "lecture_sample.pdf"

needs_tesseract = pytest.mark.skipif(
    shutil.which("tesseract") is None, reason="tesseract not installed"
)


@pytest.fixture(scope="module")
def scanned_parse():
    return PdfParser().parse(SCANNED.read_bytes())


def test_scanned_pages_are_flagged(scanned_parse):
    """The parser must notice a page it could not read.

    Without the flag the page is silently absent from the index, which is the
    failure mode that turns a refusal into a lie.
    """
    assert len(scanned_parse.units_needing_ocr) == 3
    assert len(scanned_parse.units) == 3


def test_text_pdf_is_not_flagged():
    # The fallback must not fire on documents that were read perfectly well.
    parsed = PdfParser().parse(TEXT_PDF.read_bytes())
    assert parsed.units_needing_ocr == []


def test_renderer_produces_a_png():
    image = render_pdf_page(SCANNED.read_bytes(), 1)
    assert image is not None
    assert image[:8] == b"\x89PNG\r\n\x1a\n"


def test_renderer_rejects_out_of_range_pages():
    data = SCANNED.read_bytes()
    assert render_pdf_page(data, 0) is None
    assert render_pdf_page(data, 99) is None


def test_renderer_survives_a_corrupt_file():
    # A failed render must degrade to "unreadable", not crash the whole ingest.
    assert render_pdf_page(b"not a pdf", 1) is None


@needs_tesseract
@pytest.mark.parametrize(
    ("page_no", "term"),
    [(1, "photosynthesis"), (2, "thylakoid"), (3, "calvin")],
)
def test_ocr_recovers_text_on_the_right_page(page_no, term):
    """The recovered text must stay bound to the page it came from.

    OCR that recovered the words but attached them to the wrong page would produce
    a confident citation pointing somewhere the student will not find the answer.
    """
    image = render_pdf_page(SCANNED.read_bytes(), page_no)
    text = TesseractOcrProvider().read(image).lower()
    assert term in text


@needs_tesseract
def test_ocr_does_not_leak_text_across_pages():
    page_one = TesseractOcrProvider().read(render_pdf_page(SCANNED.read_bytes(), 1)).lower()
    assert "rubisco" not in page_one, "page 3 content must not appear on page 1"


def test_missing_engine_degrades_quietly():
    """A missing engine must not fail an ingest whose other pages are fine."""
    provider = TesseractOcrProvider()
    object.__setattr__(provider, "_TesseractOcrProvider__forced", None)
    provider.__dict__["available"] = False
    assert provider.read(b"irrelevant") == ""


@needs_tesseract
def test_garbage_input_returns_empty_not_an_exception():
    assert TesseractOcrProvider().read(b"this is not a png") == ""

"""Render PDF pages to images for OCR."""

import logging

import pymupdf

logger = logging.getLogger(__name__)

# 200 DPI is the usual floor for reliable OCR on body text. Lower loses small
# characters; higher mostly costs time and memory for no accuracy gain.
OCR_DPI = 200


def render_pdf_page(data: bytes, page_no: int) -> bytes | None:
    """Render one 1-based page of a PDF to PNG bytes."""
    try:
        with pymupdf.open(stream=data, filetype="pdf") as document:
            if not 1 <= page_no <= document.page_count:
                return None
            pixmap = document[page_no - 1].get_pixmap(dpi=OCR_DPI)
            return pixmap.tobytes("png")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not render page %d for OCR: %s", page_no, exc)
        return None

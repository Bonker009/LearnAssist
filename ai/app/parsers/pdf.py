"""PDF parsing via PyMuPDF."""

import logging

import pymupdf

from app.config import get_settings
from app.models import SourceRef
from app.parsers.base import ParsedUnit, ParseResult

logger = logging.getLogger(__name__)


class PdfParser:
    def parse(self, data: bytes) -> ParseResult:
        settings = get_settings()
        result = ParseResult()

        with pymupdf.open(stream=data, filetype="pdf") as document:
            result.unit_count = document.page_count

            for index, page in enumerate(document):
                page_no = index + 1
                text = self._extract_text(page)

                # A page with almost no extractable text is a scanned image. Emit it
                # anyway, flagged, so the Phase 4 OCR pass can fill it in without a
                # second parse -- and so the page is never silently missing from the
                # index, which would make "the lecture does not cover this" a lie.
                needs_ocr = len(text.strip()) < settings.scanned_page_char_threshold
                if needs_ocr:
                    logger.info("Page %d looks scanned (%d chars)", page_no, len(text.strip()))

                result.units.append(
                    ParsedUnit(
                        text=text,
                        source=SourceRef(kind="page", page_no=page_no),
                        section_title=self._heading(page),
                        needs_ocr=needs_ocr,
                    )
                )

        return result

    @staticmethod
    def _extract_text(page) -> str:
        """Extract text in reading order.

        `get_text("blocks")` groups by layout block and sorts top-to-bottom, which
        keeps a two-column slide readable; plain `get_text()` interleaves the
        columns line by line and produces sentences that are nonsense to embed.
        """
        blocks = page.get_text("blocks", sort=True)
        # A block tuple is (x0, y0, x1, y1, text, block_no, block_type);
        # block_type 0 is text, 1 is an image.
        parts = [b[4].strip() for b in blocks if len(b) > 6 and b[6] == 0 and b[4].strip()]
        return "\n".join(parts)

    @staticmethod
    def _heading(page) -> str | None:
        """Best-effort heading: the largest text span near the top of the page."""
        try:
            data = page.get_text("dict")
        except Exception:  # noqa: BLE001
            return None

        best_size = 0.0
        best_text = None
        page_height = page.rect.height

        for block in data.get("blocks", []):
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span.get("text", "").strip()
                    size = span.get("size", 0.0)
                    top = span.get("bbox", [0, 0, 0, 0])[1]
                    # Only consider the top third; a large pull-quote lower down
                    # is not the page's heading.
                    if text and size > best_size and top < page_height / 3:
                        best_size, best_text = size, text

        if best_text and 3 <= len(best_text) <= 200:
            return best_text
        return None

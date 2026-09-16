"""Word parsing via python-docx.

Word has no page concept a parser can see -- pagination is decided by the renderer,
not stored in the file. Citing "page 4" would therefore be a guess, and a wrong
citation is worse than a vague one.

Instead the document is split at its own headings, and each section is addressed by
a running index. The `SourceRef` kind stays `page` so that retrieval, storage and
the citation UI need no special case; only the label a student reads differs.
"""

import io
import logging

from docx import Document as DocxDocument
from docx.document import Document as DocxDocumentType
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

from app.models import SourceRef
from app.parsers.base import ParsedUnit, ParseResult

logger = logging.getLogger(__name__)

# A section longer than this is split so one heading does not become a single
# enormous unit that the chunker then has to break up blindly.
MAX_SECTION_CHARS = 6000


def _iter_block_items(document: DocxDocumentType):
    """Yield paragraphs and tables in true document order.

    `document.paragraphs` and `document.tables` are separate sequences, so reading
    them one after the other puts every table at the end -- which scrambles the
    reading order and produces nonsense chunks.
    """
    body = document.element.body
    for child in body.iterchildren():
        if child.tag == qn("w:p"):
            yield Paragraph(child, document)
        elif child.tag == qn("w:tbl"):
            yield Table(child, document)


def _is_heading(paragraph: Paragraph) -> bool:
    style = (paragraph.style.name or "") if paragraph.style is not None else ""
    return style.startswith("Heading") or style == "Title"


class DocxParser:
    def parse(self, data: bytes) -> ParseResult:
        try:
            document = DocxDocument(io.BytesIO(data))
        except Exception as exc:  # noqa: BLE001 - python-docx raises several types
            raise ValueError("File is not a readable .docx document") from exc

        result = ParseResult()
        sections: list[tuple[str | None, list[str]]] = []
        current_title: str | None = None
        current_lines: list[str] = []

        def flush():
            if current_lines or current_title:
                sections.append((current_title, list(current_lines)))

        for block in _iter_block_items(document):
            if isinstance(block, Table):
                for row in block.rows:
                    cells = [c.text.strip() for c in row.cells]
                    if any(cells):
                        current_lines.append(" | ".join(cells))
                continue

            text = block.text.strip()
            if not text:
                continue

            if _is_heading(block):
                flush()
                current_title = text
                current_lines = []
            else:
                current_lines.append(text)

        flush()

        # A document with no headings at all is one long section; split it by size
        # so citations still point somewhere specific rather than at the whole file.
        if len(sections) <= 1 and sections:
            title, lines = sections[0]
            sections = [(title, part) for part in self._split_by_size(lines)]

        for index, (title, lines) in enumerate(sections, start=1):
            result.units.append(
                ParsedUnit(
                    text="\n".join(lines),
                    source=SourceRef(
                        kind="page", page_no=index,
                        label_override=f"Section {index}",
                    ),
                    section_title=title,
                )
            )

        result.unit_count = len(result.units)
        return result

    @staticmethod
    def _split_by_size(lines: list[str]) -> list[list[str]]:
        parts: list[list[str]] = []
        current: list[str] = []
        size = 0
        for line in lines:
            if size + len(line) > MAX_SECTION_CHARS and current:
                parts.append(current)
                current, size = [], 0
            current.append(line)
            size += len(line)
        if current:
            parts.append(current)
        return parts or [[]]

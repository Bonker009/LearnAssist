"""Plain text and Markdown: pasted notes, .txt and .md uploads, extracted web pages.

Like Word, text has no pages. Units are addressed by their running index and
labelled with what the student can actually find in the reader: the heading's section
number when the text has headings, otherwise the paragraph numbers it spans.
"""

import re

from app.models import SourceRef
from app.parsers.base import ParsedUnit, ParseResult

# Paragraphs are grouped up to about this size. One paragraph per unit would make
# "Paragraph 7" citations precise but leave most units too short to retrieve well.
TARGET_UNIT_CHARS = 1500
# A heading section longer than this is split by paragraph.
MAX_SECTION_CHARS = 6000

_HEADING = re.compile(r"^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$")
_BLANK_LINES = re.compile(r"\n\s*\n")


def decode_text(data: bytes) -> str:
    """Decode an upload whose encoding nobody declared.

    UTF-8 covers nearly everything, including Khmer. A BOM is stripped because it
    otherwise ends up as an invisible character at the start of the first chunk.
    """
    # Windows Notepad still saves "Unicode" as UTF-16; only trust that with a BOM,
    # since almost any byte string decodes as UTF-16 garbage.
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return data.decode("utf-16", errors="replace")
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("utf-8", errors="replace")


def _paragraphs(text: str) -> list[str]:
    return [p.strip() for p in _BLANK_LINES.split(text) if p.strip()]


def _group(paragraphs: list[str], limit: int) -> list[tuple[int, int, str]]:
    """Group consecutive paragraphs; returns (first_index, last_index, text), 1-based."""
    groups: list[tuple[int, int, str]] = []
    start = 0
    current: list[str] = []
    size = 0
    for index, paragraph in enumerate(paragraphs):
        if current and size + len(paragraph) > limit:
            groups.append((start + 1, index, "\n\n".join(current)))
            current, size, start = [], 0, index
        current.append(paragraph)
        size += len(paragraph)
    if current:
        groups.append((start + 1, len(paragraphs), "\n\n".join(current)))
    return groups


def _sections(text: str) -> list[tuple[str | None, str]]:
    """Split at Markdown headings. Text before the first heading is its own section."""
    sections: list[tuple[str | None, list[str]]] = [(None, [])]
    for line in text.splitlines():
        match = _HEADING.match(line)
        if match:
            sections.append((match.group(2).strip(), []))
        else:
            sections[-1][1].append(line)
    return [
        (title, "\n".join(lines).strip())
        for title, lines in sections
        if title or "\n".join(lines).strip()
    ]


def parse_text(text: str) -> ParseResult:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    result = ParseResult()
    sections = _sections(text)
    has_headings = any(title for title, _ in sections)

    if has_headings:
        section_no = 0
        for title, body in sections:
            section_no += 1
            parts = (
                [g[2] for g in _group(_paragraphs(body), MAX_SECTION_CHARS)]
                if len(body) > MAX_SECTION_CHARS
                else [body]
            )
            for part_no, part in enumerate(parts, start=1):
                label = f"Section {section_no}"
                if len(parts) > 1:
                    label = f"Section {section_no}.{part_no}"
                result.units.append(_unit(len(result.units) + 1, label, part, title))
    else:
        for first, last, body in _group(_paragraphs(text), TARGET_UNIT_CHARS):
            label = f"Paragraph {first}" if first == last else f"Paragraphs {first}–{last}"
            result.units.append(_unit(len(result.units) + 1, label, body, None))

    result.unit_count = len(result.units)
    return result


def _unit(index: int, label: str, text: str, title: str | None) -> ParsedUnit:
    return ParsedUnit(
        text=text,
        # kind stays `page` so retrieval, storage and the citation UI need no special
        # case; the index is what the reader scrolls to.
        source=SourceRef(kind="page", page_no=index, label_override=label[:64]),
        section_title=title[:200] if title else None,
    )


class TextParser:
    def parse(self, data: bytes) -> ParseResult:
        return parse_text(decode_text(data))

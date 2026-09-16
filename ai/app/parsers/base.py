"""Parser interface.

A parser's only job is to turn raw bytes into `ParsedUnit`s -- the smallest piece
of content that has an unambiguous source. Everything downstream (chunking,
embedding, retrieval, citation rendering) is format-agnostic, so adding a format
means adding a parser and nothing else.
"""

from dataclasses import dataclass, field
from typing import Protocol

from app.models import SourceRef


@dataclass
class ParsedUnit:
    """One slide, page, or transcript window."""

    text: str
    source: SourceRef
    section_title: str | None = None
    # Set when the unit's text came from OCR rather than an embedded text layer.
    ocr: bool = False
    # True when a PDF page yielded almost no text, i.e. it is probably scanned
    # and needs the Phase 4 OCR fallback.
    needs_ocr: bool = False


@dataclass
class ParseResult:
    units: list[ParsedUnit] = field(default_factory=list)
    # Page/slide count, or None for media.
    unit_count: int | None = None
    duration_sec: float | None = None

    @property
    def units_needing_ocr(self) -> list[ParsedUnit]:
        return [u for u in self.units if u.needs_ocr]


class Parser(Protocol):
    def parse(self, data: bytes) -> ParseResult: ...

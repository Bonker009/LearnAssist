"""Core domain models.

`Chunk` is the single abstraction every parser emits, whatever the input type.
It is what allows one retrieval path and one citation renderer to serve slides,
pages and audio alike. Adding a new input format means writing a parser that
produces these — nothing downstream changes.
"""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

SourceKind = Literal["slide", "page", "timestamp"]


class SourceRef(BaseModel):
    """Where a chunk came from, in terms a student can act on.

    Exactly one addressing scheme is populated, matching `kind`.
    """

    kind: SourceKind
    slide_no: int | None = None
    page_no: int | None = None
    start_sec: float | None = None
    end_sec: float | None = None

    @model_validator(mode="after")
    def _check_kind_fields(self) -> "SourceRef":
        if self.kind == "slide" and self.slide_no is None:
            raise ValueError("slide SourceRef requires slide_no")
        if self.kind == "page" and self.page_no is None:
            raise ValueError("page SourceRef requires page_no")
        if self.kind == "timestamp" and self.start_sec is None:
            raise ValueError("timestamp SourceRef requires start_sec")
        return self

    def label(self) -> str:
        """Human-readable citation label, e.g. 'Slide 4' or '12:30'."""
        if self.kind == "slide":
            return f"Slide {self.slide_no}"
        if self.kind == "page":
            return f"Page {self.page_no}"
        total = int(self.start_sec or 0)
        return f"{total // 60}:{total % 60:02d}"


class Chunk(BaseModel):
    """One retrievable unit of a document, bound to exactly one SourceRef."""

    document_id: UUID
    ordinal: int = Field(ge=0, description="Stable order within the document")
    text: str
    source: SourceRef
    section_title: str | None = Field(
        default=None,
        description="Slide title or PDF heading; prepended before embedding so a chunk "
        "retrieved mid-slide still carries topical context.",
    )
    # Set by the Phase 4 OCR fallback so the UI can flag machine-read text.
    ocr: bool = False

    def embedding_text(self) -> str:
        """Text actually sent to the embedding model.

        The section title is prepended here rather than stored twice on the row.
        """
        if self.section_title:
            return f"{self.section_title}\n\n{self.text}"
        return self.text


class Citation(BaseModel):
    """A source the model actually cited, resolved back from a `[n]` marker."""

    marker: int
    source: SourceRef
    label: str
    snippet: str
    ocr: bool = False


class IngestRequest(BaseModel):
    document_id: UUID
    storage_key: str
    filename: str
    content_type: str


class QueryRequest(BaseModel):
    document_id: UUID
    question: str = Field(min_length=1, max_length=2000)


class QueryResponse(BaseModel):
    answer: str
    citations: list[Citation]
    grounded: bool = Field(
        description="False when the model reported the lecture does not cover the question."
    )

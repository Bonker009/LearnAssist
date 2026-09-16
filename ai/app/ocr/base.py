"""OCR provider interface.

Kept behind an interface for the same reason as embeddings and the LLM: the engine
is an implementation detail, and swapping Tesseract for PaddleOCR should not touch
the ingestion pipeline.
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class OcrProvider(Protocol):
    @property
    def available(self) -> bool:
        """Whether the engine is actually installed.

        Checked rather than assumed: OCR is an optional extra, and a missing engine
        must degrade to "this page could not be read" rather than crash an ingest
        whose other pages are perfectly fine.
        """
        ...

    def read(self, image_png: bytes) -> str:
        """Extract text from a rendered page image."""
        ...

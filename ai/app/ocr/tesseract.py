"""Tesseract OCR provider.

Chosen over PaddleOCR because paddlepaddle is a several-hundred-megabyte wheel and
this is a fallback path most ingests never take -- it would slow every image build
to serve the minority of uploads that are scanned. PaddleOCR generally reads
complex layouts better, so it stays a supported swap behind `OcrProvider`.
"""

import functools
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


class TesseractOcrProvider:
    def __init__(self, language: str = "eng") -> None:
        self._language = language

    @functools.cached_property
    def available(self) -> bool:
        return shutil.which("tesseract") is not None

    def read(self, image_png: bytes) -> str:
        if not self.available:
            return ""

        source = Path(tempfile.mkstemp(suffix=".png")[1])
        source.write_bytes(image_png)
        try:
            result = subprocess.run(
                # `--psm 3` is full automatic page segmentation, which is right for
                # a whole rendered page rather than a cropped line.
                ["tesseract", str(source), "stdout", "-l", self._language, "--psm", "3"],
                capture_output=True,
                timeout=120,
            )
            if result.returncode != 0:
                logger.warning("tesseract failed: %s", result.stderr.decode(errors="replace")[:200])
                return ""
            return result.stdout.decode(errors="replace").strip()
        except subprocess.TimeoutExpired:
            logger.warning("tesseract timed out on a page")
            return ""
        finally:
            source.unlink(missing_ok=True)


@functools.cache
def get_ocr_provider() -> TesseractOcrProvider:
    return TesseractOcrProvider()

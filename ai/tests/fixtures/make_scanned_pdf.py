"""Build a genuinely scanned PDF: pages that are images, with no text layer.

Rendering the text fixture to images and re-wrapping them is the only honest way
to test the OCR path. A PDF that merely *looks* scanned but retains a text layer
would be read by the normal parser and never exercise OCR at all.
"""

import pathlib

import pymupdf

HERE = pathlib.Path(__file__).parent
SOURCE = HERE / "lecture_sample.pdf"
TARGET = HERE / "lecture_scanned.pdf"
# 120 DPI JPEG keeps the fixture small enough to commit while staying legible
# to OCR. Real scans are usually 200-300 DPI; the renderer uses 200.
DPI = 120
JPEG_QUALITY = 60


def build() -> int:
    with pymupdf.open(SOURCE) as text_pdf, pymupdf.open() as image_pdf:
        for page in text_pdf:
            pixmap = page.get_pixmap(dpi=DPI)
            new_page = image_pdf.new_page(width=page.rect.width, height=page.rect.height)
            jpeg = pixmap.tobytes("jpeg", jpg_quality=JPEG_QUALITY)
            new_page.insert_image(new_page.rect, stream=jpeg)
        image_pdf.save(TARGET, deflate=True, garbage=4)
    return TARGET.stat().st_size


if __name__ == "__main__":
    size = build()
    with pymupdf.open(TARGET) as check:
        extractable = sum(len(p.get_text().strip()) for p in check)
    print(f"wrote {TARGET.name} ({size} bytes)")
    print(f"extractable text characters: {extractable} (must be 0 for a real scan)")

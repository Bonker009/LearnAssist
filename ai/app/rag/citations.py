"""Resolve and validate the `[n]` markers a model emits.

A model will occasionally cite a block that was never given to it -- a citation
to nothing, attached to a claim that is therefore unsupported. Rendering that in
the UI would be worse than showing no citation at all, because the chip implies
the claim was verified. Invented markers are stripped here, in code, rather than
being prevented by prompt wording alone.
"""

import re

from app.models import Chunk, Citation

_MARKER_RE = re.compile(r"\[(\d{1,3})\]")

NOT_COVERED = "The lecture does not cover this."


def resolve_citations(answer: str, blocks: dict[int, Chunk]) -> tuple[str, list[Citation]]:
    """Strip invalid markers and return the citations that survive.

    @return the cleaned answer and the cited sources, in order of first appearance.
    """
    cited: dict[int, Citation] = {}
    invalid: set[int] = set()

    for match in _MARKER_RE.finditer(answer):
        marker = int(match.group(1))
        chunk = blocks.get(marker)
        if chunk is None:
            invalid.add(marker)
            continue
        if marker not in cited:
            cited[marker] = Citation(
                marker=marker,
                source=chunk.source,
                label=chunk.source.label(),
                snippet=snippet(chunk.text),
                ocr=chunk.ocr,
            )

    cleaned = answer
    for marker in invalid:
        cleaned = cleaned.replace(f"[{marker}]", "")
    # Removing a marker leaves a double space or a space before punctuation.
    cleaned = re.sub(r" {2,}", " ", cleaned)
    cleaned = re.sub(r"\s+([.,;:])", r"\1", cleaned).strip()

    return cleaned, list(cited.values())


def is_grounded(answer: str, citations: list[Citation]) -> bool:
    """Whether the answer actually rests on the lecture.

    An answer with no surviving citation is treated as ungrounded even if the
    model did not use the refusal phrase, so the UI can mark it rather than
    presenting an unsupported claim as if it were sourced.
    """
    if NOT_COVERED.lower() in answer.lower():
        return False
    return bool(citations)


def snippet(text: str, limit: int = 240) -> str:
    """Short excerpt shown under a citation or quiz answer."""
    collapsed = " ".join(text.split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[:limit].rsplit(" ", 1)[0] + "..."

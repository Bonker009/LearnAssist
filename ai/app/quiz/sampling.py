"""Choose which parts of a document a quiz should cover."""

from app.models import Chunk


def stratified_sample(chunks: list[Chunk], target: int) -> list[Chunk]:
    """Spread the selection evenly across the document by ordinal.

    Deliberately not a similarity search against some generic query: doing that
    concentrates every question on whatever the document says about its own topic
    up front, so a student revising a 60-slide lecture gets ten questions about
    slide 1. Even coverage is the whole point of a practice quiz.

    Longer chunks are preferred within each band, because a two-line chunk rarely
    contains enough to build a non-trivial question from.
    """
    if not chunks:
        return []

    ordered = sorted(chunks, key=lambda c: c.ordinal)
    if len(ordered) <= target:
        return ordered

    band_size = len(ordered) / target
    selected: list[Chunk] = []
    used: set[int] = set()

    for index in range(target):
        start = int(index * band_size)
        end = max(int((index + 1) * band_size), start + 1)
        band = [c for c in ordered[start:end] if c.ordinal not in used]
        if not band:
            continue
        best = max(band, key=lambda c: len(c.text))
        used.add(best.ordinal)
        selected.append(best)

    return selected

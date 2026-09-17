"""Group raw transcript segments into citable windows.

Whisper emits short segments, often a clause each. Indexing them one-to-one gives
retrieval almost nothing to work with -- a five-word fragment has no context to
embed -- and produces citations so granular they are useless to a student.

Grouping into roughly 45-second windows that end on sentence boundaries keeps each
unit substantial enough to retrieve well while staying precise enough that seeking
to its start actually lands on the relevant explanation.
"""

from dataclasses import dataclass

from app.models import SourceRef
from app.parsers.base import ParsedUnit

TARGET_WINDOW_SEC = 45.0
# A window is allowed to overrun the target to reach a sentence boundary, but not
# without limit -- otherwise an unpunctuated monologue becomes one huge unit.
MAX_WINDOW_SEC = 75.0
# ។ (khan) and ៕ (bariyoosan) end sentences in Khmer.
_SENTENCE_ENDINGS = (".", "!", "?", "。", "？", "！", "។", "៕")


@dataclass
class Segment:
    start: float
    end: float
    text: str


def _ends_sentence(text: str) -> bool:
    return text.rstrip().endswith(_SENTENCE_ENDINGS)


def group_segments(segments: list[Segment]) -> list[ParsedUnit]:
    units: list[ParsedUnit] = []
    current: list[Segment] = []

    def flush():
        if not current:
            return
        text = " ".join(s.text.strip() for s in current if s.text.strip()).strip()
        if not text:
            return
        units.append(
            ParsedUnit(
                text=text,
                source=SourceRef(
                    kind="timestamp",
                    start_sec=round(current[0].start, 2),
                    end_sec=round(current[-1].end, 2),
                ),
            )
        )

    for segment in segments:
        current.append(segment)
        span = current[-1].end - current[0].start

        # The span is measured over the window as it now stands, including this
        # segment, because this segment is what the window will actually contain.
        # Deciding before appending measures one window but emits another, and
        # every window comes out one segment short of the target.
        if span >= TARGET_WINDOW_SEC and _ends_sentence(segment.text):
            flush()
            current = []
        elif span >= MAX_WINDOW_SEC:
            # The speaker never reached a sentence boundary; cut anyway rather
            # than let one window swallow the whole recording.
            flush()
            current = []

    flush()
    return units

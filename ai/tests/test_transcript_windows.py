"""Transcript windowing decides how precise a media citation is."""

import pytest

from app.transcribe.windows import (
    MAX_WINDOW_SEC,
    TARGET_WINDOW_SEC,
    Segment,
    group_segments,
)


def _speech(count: int, step: float = 5.0, end_sentences: bool = True):
    """Build `count` segments of `step` seconds each."""
    return [
        Segment(
            start=i * step,
            end=(i + 1) * step,
            text=f"Sentence {i} about the topic" + ("." if end_sentences else ""),
        )
        for i in range(count)
    ]


def test_short_recording_is_one_window():
    units = group_segments(_speech(4))  # 20s total
    assert len(units) == 1
    assert units[0].source.start_sec == 0.0
    assert units[0].source.end_sec == 20.0


def test_every_unit_is_a_timestamp_reference():
    for unit in group_segments(_speech(40)):
        assert unit.source.kind == "timestamp"
        assert unit.source.start_sec is not None
        assert unit.source.end_sec is not None
        # A timestamp chunk must not also claim a page or slide.
        assert unit.source.page_no is None
        assert unit.source.slide_no is None


def test_windows_are_near_the_target_length():
    units = group_segments(_speech(40))  # 200s total
    assert len(units) > 1
    for unit in units[:-1]:  # the final window is whatever remains
        span = unit.source.end_sec - unit.source.start_sec
        assert span >= TARGET_WINDOW_SEC


def test_windows_do_not_overlap_or_gap():
    units = group_segments(_speech(40))
    for earlier, later in zip(units, units[1:]):
        assert later.source.start_sec >= earlier.source.end_sec


def test_windows_prefer_sentence_boundaries():
    units = group_segments(_speech(40))
    for unit in units[:-1]:
        assert unit.text.rstrip().endswith("."), "window should close on a sentence"


def test_unpunctuated_speech_is_still_bounded():
    """A speaker who never pauses must not produce one enormous unit.

    Without a hard cap, a lecture with no detectable sentence endings would become
    a single chunk citable only as "the whole recording".
    """
    units = group_segments(_speech(60, end_sentences=False))
    assert len(units) > 1
    for unit in units:
        span = unit.source.end_sec - unit.source.start_sec
        assert span <= MAX_WINDOW_SEC + 5.0


def test_empty_input_produces_nothing():
    assert group_segments([]) == []


def test_blank_segments_are_dropped():
    segments = [
        Segment(start=0.0, end=5.0, text="   "),
        Segment(start=5.0, end=10.0, text="Real speech."),
    ]
    units = group_segments(segments)
    assert len(units) == 1
    assert units[0].text == "Real speech."


def test_timestamp_label_is_seekable():
    units = group_segments(_speech(40))
    # 1:15 is something a student can act on; 75.0 is not.
    assert ":" in units[1].source.label()


@pytest.mark.parametrize("count", [1, 2, 7, 13, 50])
def test_no_segment_text_is_lost(count):
    segments = _speech(count)
    combined = " ".join(u.text for u in group_segments(segments))
    for segment in segments:
        assert segment.text.strip() in combined

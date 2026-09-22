"""End-to-end speech-to-text, on real synthesised speech.

Marked `slow` because it downloads the Whisper weights on first run. It is worth
the cost: the windowing unit tests prove the grouping arithmetic, but only this
proves that audio actually becomes citable text with usable timestamps.

Requires espeak-ng to synthesise the input:
    apt-get install -y espeak-ng
"""

import asyncio
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from app.transcribe.whisper import WhisperTranscriber

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(shutil.which("espeak-ng") is None, reason="espeak-ng not installed"),
]

SPOKEN = (
    "Photosynthesis occurs in the chloroplasts of plant cells. "
    "The Calvin cycle fixes carbon dioxide in the stroma."
)


@pytest.fixture(scope="module")
def transcript():
    wav = Path(tempfile.mkstemp(suffix=".wav")[1])
    subprocess.run(
        ["espeak-ng", "-w", str(wav), "-s", "130", SPOKEN],
        check=True, capture_output=True,
    )
    try:
        return asyncio.run(WhisperTranscriber().parse(wav.read_bytes(), suffix=".wav"))
    finally:
        wav.unlink(missing_ok=True)


def test_produces_timestamped_units(transcript):
    assert transcript.units, "speech should produce at least one unit"
    for unit in transcript.units:
        assert unit.source.kind == "timestamp"
        assert unit.source.start_sec is not None
        assert unit.source.end_sec > unit.source.start_sec


def test_duration_is_reported(transcript):
    # Used by the UI to show recording length, and by the player to seek.
    assert transcript.duration_sec > 1.0


def test_media_has_no_page_count(transcript):
    # A recording has a duration, not pages; asserting a unit_count would be a lie.
    assert transcript.unit_count is None


@pytest.mark.parametrize("term", ["photosynthesis", "calvin cycle", "carbon dioxide"])
def test_key_terms_are_transcribed(transcript, term):
    """Assert on domain terms, not an exact string.

    A small model on synthesised speech makes minor errors ("stroma" -> "stromo",
    "photosynthesis" -> "photo synthesis"), and a test that demanded a perfect
    transcript would fail for reasons that do not affect whether a student can find
    the right moment in the lecture. Spaces are ignored for the same reason.
    """
    combined = "".join(u.text for u in transcript.units).lower().replace(" ", "")
    assert term.replace(" ", "") in combined


def test_timestamps_are_within_the_recording(transcript):
    for unit in transcript.units:
        assert 0 <= unit.source.start_sec <= transcript.duration_sec + 1

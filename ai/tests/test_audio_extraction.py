"""FFmpeg extraction, tested against real media rather than a mock.

The failure modes here are all about the shape of the output -- wrong sample rate,
stereo instead of mono, a video container Whisper cannot open -- and a mocked
subprocess would assert none of them.
"""

import asyncio
import shutil
import struct
import subprocess
import tempfile
from pathlib import Path

import pytest

from app.transcribe.audio import extract_audio, probe_duration

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None, reason="ffmpeg not installed"
)


def _make_media(suffix: str, seconds: int = 3) -> bytes:
    """Synthesise a real media file with ffmpeg."""
    target = Path(tempfile.mkstemp(suffix=suffix)[1])
    if suffix == ".mp4":
        args = [
            "ffmpeg", "-y", "-f", "lavfi", "-i", f"testsrc=duration={seconds}:size=128x96:rate=10",
            "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
            "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac",
            "-shortest", str(target),
        ]
    else:
        args = [
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", f"sine=frequency=440:duration={seconds}:sample_rate=44100",
            "-ac", "2", str(target),
        ]
    subprocess.run(args, check=True, capture_output=True)
    data = target.read_bytes()
    target.unlink(missing_ok=True)
    return data


def _wav_header(path: Path) -> tuple[int, int, int]:
    """@return (channels, sample_rate, bits_per_sample) from the fmt chunk."""
    raw = path.read_bytes()
    index = raw.index(b"fmt ") + 8
    channels, rate = struct.unpack_from("<HI", raw, index + 2)
    bits = struct.unpack_from("<H", raw, index + 14)[0]
    return channels, rate, bits


def test_extracts_mono_16k_from_stereo_audio():
    """Whisper wants 16 kHz mono; anything else makes it resample internally."""
    data = _make_media(".wav")
    path, duration = asyncio.run(extract_audio(data, ".wav"))
    try:
        channels, rate, bits = _wav_header(path)
        assert channels == 1, "must be downmixed to mono"
        assert rate == 16000, "must be resampled to 16 kHz"
        assert bits == 16
        assert duration == pytest.approx(3.0, abs=0.3)
    finally:
        path.unlink(missing_ok=True)


def test_extracts_audio_track_from_video():
    """A lecture recording is usually a video; the video stream must be dropped."""
    data = _make_media(".mp4")
    path, duration = asyncio.run(extract_audio(data, ".mp4"))
    try:
        channels, rate, _ = _wav_header(path)
        assert channels == 1
        assert rate == 16000
        assert duration == pytest.approx(3.0, abs=0.4)
        assert path.stat().st_size > 1000
    finally:
        path.unlink(missing_ok=True)


def test_unreadable_file_raises_a_useful_error():
    with pytest.raises(ValueError, match="Could not read this media file"):
        asyncio.run(extract_audio(b"this is not media", ".mp4"))


def test_temp_files_are_cleaned_up_on_failure():
    """A failed ingest must not leave the source file behind.

    Lecture recordings are hundreds of megabytes; leaking one per failed upload
    fills the container's disk quickly.
    """
    before = set(Path(tempfile.gettempdir()).glob("*"))
    with pytest.raises(ValueError):
        asyncio.run(extract_audio(b"not media at all", ".mp4"))
    after = set(Path(tempfile.gettempdir()).glob("*"))
    assert len(after - before) == 0


def test_probe_duration_on_missing_file_returns_zero():
    assert asyncio.run(probe_duration(Path("/nonexistent.wav"))) == 0.0

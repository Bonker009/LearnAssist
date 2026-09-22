"""Qwen3-ASR windowing: the cuts that turn one recording into timestamped segments.

Qwen3-ASR returns no timestamps, so a transcript's timing comes entirely from where
these windows start and end. They must cover the recording exactly, with no gaps or
overlaps, or a citation seeks to the wrong moment.
"""

import tempfile
import wave
from pathlib import Path

import numpy as np
import pytest

from app.transcribe import qwen
from app.transcribe.qwen import SAMPLE_RATE, WINDOW_SEC, split_windows


def _write_wav(samples: np.ndarray) -> Path:
    path = Path(tempfile.mkstemp(suffix=".wav")[1])
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes((np.clip(samples, -1, 1) * 32767).astype(np.int16).tobytes())
    return path


def _tone(seconds: float) -> np.ndarray:
    t = np.arange(int(seconds * SAMPLE_RATE)) / SAMPLE_RATE
    return (0.3 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)


@pytest.fixture
def wav_file():
    paths: list[Path] = []

    def make(samples: np.ndarray) -> Path:
        paths.append(_write_wav(samples))
        return paths[-1]

    yield make
    for path in paths:
        path.unlink(missing_ok=True)


@pytest.mark.parametrize("seconds", [0.5, 29.0, 30.0, 61.0, 185.3])
def test_windows_cover_recording_without_gaps(wav_file, seconds):
    windows = list(split_windows(wav_file(_tone(seconds))))

    expected_start = 0.0
    total = 0
    for start, samples in windows:
        assert start == pytest.approx(expected_start, abs=1e-6)
        expected_start += len(samples) / SAMPLE_RATE
        total += len(samples)
    assert total == int(seconds * SAMPLE_RATE)


def test_windows_stay_near_target_length(wav_file):
    windows = list(split_windows(wav_file(_tone(200))))
    for _, samples in windows[:-1]:
        length = len(samples) / SAMPLE_RATE
        assert WINDOW_SEC - qwen.SEARCH_SEC <= length <= WINDOW_SEC


def test_cut_lands_in_a_pause(wav_file):
    """A pause inside the search zone is where the cut must fall, not mid-sound."""
    pause_at = 27.0
    audio = np.concatenate([_tone(pause_at), np.zeros(SAMPLE_RATE // 2, np.float32), _tone(20)])
    (_, first), *_ = split_windows(wav_file(audio))
    assert pause_at <= len(first) / SAMPLE_RATE <= pause_at + 0.5


def test_empty_recording_has_no_windows(wav_file):
    assert list(split_windows(wav_file(np.zeros(0, np.float32)))) == []


def test_silent_windows_are_not_sent_to_the_model(wav_file, monkeypatch):
    calls: list[int] = []

    class FakeModel:
        def transcribe(self, audio, language):
            calls.append(len(audio))
            return [type("R", (), {"text": "hello."})() for _ in audio]

    monkeypatch.setattr(qwen, "_load_model", lambda: FakeModel())
    audio = np.concatenate([np.zeros(40 * SAMPLE_RATE, np.float32), _tone(10)])
    segments = qwen.transcribe_path(wav_file(audio), "en", 50.0)

    assert sum(calls) == 1
    assert len(segments) == 1
    assert segments[0].start > 20  # the silent opening was skipped, not re-timed
    assert segments[0].end == pytest.approx(50.0)


def test_khmer_is_not_routed_to_qwen():
    # Qwen3-ASR has no Khmer; routing it there would silently produce garbage.
    assert "km" not in qwen.QWEN_LANGUAGES
    assert "en" in qwen.QWEN_LANGUAGES

"""Speech-to-text via Qwen3-ASR.

Qwen3-ASR is more accurate than Whisper on the languages it covers, but it covers 30
of them and Khmer is not one, so `whisper.py` routes Khmer (and anything else outside
`QWEN_LANGUAGES`) to Whisper and only hands supported audio to this module.

Qwen3-ASR returns text, not timestamps. Its companion forced aligner would add them,
but it supports only 11 languages and 5 minutes of audio per call. Instead the audio
is cut into ~30-second windows here, each cut placed at the quietest moment near the
boundary so a word is rarely split, and each window becomes one `Segment` spanning
exactly the audio it came from. `group_segments` then merges those into the usual
~45-second citable units, so window-level timing is all a citation needs.
"""

import logging
import threading
import wave
from collections.abc import Callable, Iterator
from pathlib import Path

import numpy as np

from app.config import get_settings
from app.transcribe.windows import Segment

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16_000  # what `audio.FFMPEG_ARGS` produces

# ISO 639-1 (as Whisper reports it) -> the English name Qwen3-ASR's `language` takes.
QWEN_LANGUAGES = {
    "zh": "Chinese", "en": "English", "yue": "Cantonese", "ar": "Arabic", "de": "German",
    "fr": "French", "es": "Spanish", "pt": "Portuguese", "id": "Indonesian",
    "it": "Italian", "ko": "Korean", "ru": "Russian", "th": "Thai", "vi": "Vietnamese",
    "ja": "Japanese", "tr": "Turkish", "hi": "Hindi", "ms": "Malay", "nl": "Dutch",
    "sv": "Swedish", "da": "Danish", "fi": "Finnish", "pl": "Polish", "cs": "Czech",
    "fil": "Filipino", "tl": "Filipino", "fa": "Persian", "el": "Greek", "hu": "Hungarian",
    "mk": "Macedonian", "ro": "Romanian",
}

# Windows aim for WINDOW_SEC and are cut at the quietest FRAME_SEC frame within the
# final SEARCH_SEC, so a cut lands in a pause rather than mid-word.
WINDOW_SEC = 30.0
SEARCH_SEC = 6.0
FRAME_SEC = 0.1
# Below this RMS (on a -1..1 scale) a window is treated as silence and skipped: an
# ASR model fed pure silence tends to invent a phrase to fill it.
SILENCE_RMS = 0.004

_model = None
_model_lock = threading.Lock()


def _load_model():
    """Load Qwen3-ASR once, lazily, for the same reasons as Whisper's loader."""
    global _model
    with _model_lock:
        if _model is not None:
            return _model

        import torch
        from qwen_asr import Qwen3ASRModel

        settings = get_settings()
        device = settings.qwen_asr_device
        # bfloat16 halves memory on a GPU; most CPUs have no fast bf16 path.
        dtype = torch.float32 if device == "cpu" else torch.bfloat16

        logger.info("Loading Qwen3-ASR model=%s device=%s", settings.qwen_asr_model, device)
        _model = Qwen3ASRModel.from_pretrained(
            settings.qwen_asr_model,
            dtype=dtype,
            device_map=device,
            max_inference_batch_size=settings.qwen_asr_batch_size,
            max_new_tokens=512,  # 30 s of fast speech in a dense script stays well under
        )
        return _model


def _cut_point(tail: np.ndarray) -> int:
    """Sample offset of the quietest frame in `tail`, measured from its start."""
    frame = int(FRAME_SEC * SAMPLE_RATE)
    frames = len(tail) // frame
    if frames == 0:
        return len(tail)
    energy = np.square(tail[: frames * frame]).reshape(frames, frame).mean(axis=1)
    return int(np.argmin(energy)) * frame + frame // 2


def split_windows(path: Path) -> Iterator[tuple[float, np.ndarray]]:
    """Yield `(start_sec, samples)` windows covering the whole WAV, in order.

    Reads incrementally: a four-hour lecture is ~900 MB as float32, and only one
    window of it is needed at a time.
    """
    window = int(WINDOW_SEC * SAMPLE_RATE)
    search = int(SEARCH_SEC * SAMPLE_RATE)

    with wave.open(str(path), "rb") as wav:
        if wav.getframerate() != SAMPLE_RATE or wav.getnchannels() != 1:
            raise ValueError("expected 16 kHz mono audio from extract_audio")

        buffer = np.zeros(0, dtype=np.float32)
        offset = 0  # samples already yielded
        exhausted = False
        while True:
            if not exhausted and len(buffer) < window:
                raw = wav.readframes(window - len(buffer))
                if raw:
                    chunk = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
                    buffer = np.concatenate([buffer, chunk])
                exhausted = len(buffer) < window
            if len(buffer) == 0:
                return
            if exhausted:
                yield offset / SAMPLE_RATE, buffer
                return

            cut = window - search + _cut_point(buffer[window - search :])
            yield offset / SAMPLE_RATE, buffer[:cut]
            offset += cut
            buffer = buffer[cut:]


def transcribe_path(
    path: Path,
    language: str,
    duration: float,
    on_progress: Callable[[float], None] | None = None,
) -> list[Segment]:
    """Transcribe a 16 kHz mono WAV into one segment per audio window.

    @param language an ISO code present in `QWEN_LANGUAGES`
    """
    model = _load_model()
    name = QWEN_LANGUAGES[language]
    batch_size = max(1, get_settings().qwen_asr_batch_size)

    segments: list[Segment] = []
    batch: list[tuple[float, np.ndarray]] = []

    def flush() -> None:
        if not batch:
            return
        results = model.transcribe(
            audio=[(samples, SAMPLE_RATE) for _, samples in batch],
            language=[name] * len(batch),
        )
        for (start, samples), result in zip(batch, results, strict=True):
            text = (result.text or "").strip()
            if text:
                end = start + len(samples) / SAMPLE_RATE
                segments.append(Segment(start=start, end=end, text=text))
        if on_progress and duration:
            last_start, last_samples = batch[-1]
            on_progress(min((last_start + len(last_samples) / SAMPLE_RATE) / duration, 1.0))
        batch.clear()

    for start, samples in split_windows(path):
        if float(np.sqrt(np.mean(np.square(samples)))) < SILENCE_RMS:
            continue
        batch.append((start, samples))
        if len(batch) >= batch_size:
            flush()
    flush()
    return segments

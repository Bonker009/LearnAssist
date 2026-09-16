"""Speech-to-text via faster-whisper."""

import asyncio
import logging
import os
from collections.abc import Callable
from pathlib import Path

from app.parsers.base import ParsedUnit, ParseResult
from app.transcribe.audio import extract_audio
from app.transcribe.windows import Segment, group_segments

logger = logging.getLogger(__name__)

_model = None


def _load_model():
    """Load the Whisper model once, lazily.

    Lazily because the weights are hundreds of megabytes: importing this module
    during a PDF ingest, or during the test suite, must not pay that cost.
    """
    global _model
    if _model is not None:
        return _model

    from faster_whisper import WhisperModel

    size = os.getenv("WHISPER_MODEL", "small")
    device = os.getenv("WHISPER_DEVICE", "cpu")
    # int8 on CPU is the difference between "slow" and "unusable" for an
    # hour-long lecture; float16 is the right choice when a GPU is present.
    compute = os.getenv("WHISPER_COMPUTE", "int8" if device == "cpu" else "float16")

    logger.info("Loading Whisper model=%s device=%s compute=%s", size, device, compute)
    _model = WhisperModel(size, device=device, compute_type=compute)
    return _model


def _transcribe_sync(path: Path, on_progress: Callable[[float], None] | None):
    model = _load_model()
    segments, info = model.transcribe(
        str(path),
        beam_size=5,
        # Silence between slides is common in a recorded lecture and Whisper will
        # cheerfully hallucinate words into it.
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 500},
    )

    collected: list[Segment] = []
    duration = info.duration or 0.0
    for segment in segments:
        collected.append(Segment(start=segment.start, end=segment.end, text=segment.text))
        if on_progress and duration:
            on_progress(min(segment.end / duration, 1.0))

    return collected, duration, info.language


class WhisperTranscriber:
    """Turns an audio or video upload into timestamped, citable units."""

    async def parse(
        self, data: bytes, suffix: str = "", on_progress: Callable[[float], None] | None = None
    ) -> ParseResult:
        audio_path, duration = await extract_audio(data, suffix)
        try:
            # faster-whisper is synchronous and CPU-bound; running it inline would
            # block the event loop and stall every other request for minutes.
            segments, model_duration, language = await asyncio.to_thread(
                _transcribe_sync, audio_path, on_progress
            )
        finally:
            audio_path.unlink(missing_ok=True)

        logger.info(
            "Transcribed %.1fs of %s audio into %d segments",
            model_duration or duration, language, len(segments),
        )

        result = ParseResult()
        result.units = group_segments(segments)
        result.duration_sec = duration or model_duration
        result.unit_count = None  # media has a duration, not a page count
        return result

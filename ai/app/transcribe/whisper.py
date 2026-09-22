"""Speech-to-text: routes each recording to Qwen3-ASR or faster-whisper.

With `SPEECH_BACKEND=qwen` (the default), audio in a language Qwen3-ASR supports is
transcribed by it (`qwen.py`). Khmer is not among them, so Khmer, and any other
language Qwen does not cover, stays on Whisper. Whisper's base model (`WHISPER_MODEL`)
also does the language detection that decides the route, because Qwen cannot detect
a language it was never trained on. Khmer gets a dedicated Whisper fine-tune
(`WHISPER_MODEL_KM`), because the stock multilingual checkpoints transcribe Khmer
badly enough to make the resulting index useless.

`SPEECH_BACKEND=whisper` restores the Whisper-only behaviour.
"""

import asyncio
import logging
import threading
import wave
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from app.config import get_settings
from app.parsers.base import ParseResult
from app.transcribe import qwen
from app.transcribe.audio import extract_audio, extract_audio_from_path
from app.transcribe.windows import Segment, group_segments

logger = logging.getLogger(__name__)

_models: dict[str, object] = {}
_models_lock = threading.Lock()


def _load_model(name: str):
    """Load a Whisper model once, lazily.

    Lazily because the weights are hundreds of megabytes: importing this module
    during a PDF ingest, or during the test suite, must not pay that cost. Locked
    because dictation and a lecture ingest can ask for the same model concurrently
    from two worker threads.
    """
    with _models_lock:
        if name in _models:
            return _models[name]

        import os

        from faster_whisper import WhisperModel

        device = os.getenv("WHISPER_DEVICE", "cpu")
        # int8 on CPU is the difference between "slow" and "unusable" for an
        # hour-long lecture; float16 is the right choice when a GPU is present.
        compute = os.getenv("WHISPER_COMPUTE", "int8" if device == "cpu" else "float16")

        logger.info("Loading Whisper model=%s device=%s compute=%s", name, device, compute)
        _models[name] = WhisperModel(name, device=device, compute_type=compute)
        return _models[name]


def _base_model_name() -> str:
    import os

    return os.getenv("WHISPER_MODEL", "small")


def _model_for(language: str | None) -> str:
    khmer = get_settings().whisper_model_km
    if language == "km" and khmer:
        return khmer
    return _base_model_name()


@dataclass
class Transcript:
    segments: list[Segment]
    duration: float
    language: str


def _run(model_name: str, path: Path, language: str | None):
    model = _load_model(model_name)
    return model.transcribe(
        str(path),
        language=language,
        task="transcribe",
        beam_size=5,
        # Silence between slides is common in a recorded lecture and Whisper will
        # cheerfully hallucinate words into it.
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 500},
    )


def _transcribe_sync(
    path: Path,
    on_progress: Callable[[float], None] | None,
    language: str | None = None,
) -> Transcript:
    """Transcribe with whichever engine suits the audio's language.

    Whisper's `transcribe` returns a lazy segment generator but detects the language
    up front, so checking `info.language` and then switching model or engine costs a
    detection pass, not a wasted transcription.
    """
    use_qwen = get_settings().speech_backend == "qwen"
    if use_qwen and language in qwen.QWEN_LANGUAGES:
        # The caller named a language Qwen covers; no detection pass needed.
        return _transcribe_qwen(path, language, on_progress)

    segments, info = _run(_model_for(language), path, language)

    if use_qwen and language is None and info.language in qwen.QWEN_LANGUAGES:
        logger.info(
            "Detected %s (p=%.2f); transcribing with Qwen3-ASR",
            info.language, info.language_probability,
        )
        return _transcribe_qwen(path, info.language, on_progress, info.duration)

    if language is None and info.language == "km":
        khmer = _model_for("km")
        if khmer != _base_model_name():
            logger.info(
                "Detected Khmer (p=%.2f); switching to %s", info.language_probability, khmer
            )
            segments, info = _run(khmer, path, "km")

    collected: list[Segment] = []
    duration = info.duration or 0.0
    for segment in segments:
        collected.append(Segment(start=segment.start, end=segment.end, text=segment.text))
        if on_progress and duration:
            on_progress(min(segment.end / duration, 1.0))

    return Transcript(collected, duration, info.language)


def _transcribe_qwen(
    path: Path,
    language: str,
    on_progress: Callable[[float], None] | None,
    duration: float | None = None,
) -> Transcript:
    if not duration:
        with wave.open(str(path), "rb") as wav:
            duration = wav.getnframes() / wav.getframerate()
    segments = qwen.transcribe_path(path, language, duration, on_progress)
    return Transcript(segments, duration, language)


class WhisperTranscriber:
    """Turns an audio or video upload into timestamped, citable units."""

    async def parse(
        self, data: bytes, suffix: str = "", on_progress: Callable[[float], None] | None = None
    ) -> ParseResult:
        audio_path, duration = await extract_audio(data, suffix)
        return await self._parse_wav(audio_path, duration, on_progress)

    async def parse_file(
        self, source: Path, on_progress: Callable[[float], None] | None = None
    ) -> ParseResult:
        """As `parse`, for media already on disk. The caller still owns `source`."""
        audio_path, duration = await extract_audio_from_path(source)
        return await self._parse_wav(audio_path, duration, on_progress)

    async def _parse_wav(
        self, audio_path: Path, duration: float, on_progress: Callable[[float], None] | None
    ) -> ParseResult:
        try:
            # Both engines are synchronous and CPU-bound; running them inline would
            # block the event loop and stall every other request for minutes.
            transcript = await asyncio.to_thread(_transcribe_sync, audio_path, on_progress)
        finally:
            audio_path.unlink(missing_ok=True)

        logger.info(
            "Transcribed %.1fs of %s audio into %d segments",
            transcript.duration or duration, transcript.language, len(transcript.segments),
        )

        result = ParseResult()
        result.units = group_segments(transcript.segments)
        result.duration_sec = duration or transcript.duration
        result.unit_count = None  # media has a duration, not a page count
        return result


def choose_dictation_language(probs: dict[str, float], min_prob: float) -> str:
    """Pick a voice message's language: any language, with Khmer as the fallback.

    Whisper's multilingual checkpoints recognise most languages confidently (English,
    French, Chinese, Vietnamese and Thai at 0.92-1.0 on short clips) but not Khmer,
    which they mistake for Vietnamese, Thai or English at 0.3-0.87. So a detected
    language is trusted only when it is confident and far ahead of Khmer; otherwise the
    clip is Khmer, which is what an uncertain clip from these students most likely is.
    """
    khmer = probs.get("km", 0.0)
    language, probability = max(probs.items(), key=lambda item: item[1], default=("km", 0.0))
    if language == "km":
        return "km"
    return language if probability >= min_prob and probability >= 50 * khmer else "km"


def _detect_dictation_language(path: Path) -> str:
    from faster_whisper import decode_audio
    from faster_whisper.vad import VadOptions

    model = _load_model(_base_model_name())
    # Unlike transcribe(), detect_language() takes VadOptions, not a dict.
    _, _, all_probs = model.detect_language(
        decode_audio(str(path)),
        vad_filter=True,
        vad_parameters=VadOptions(min_silence_duration_ms=500),
    )
    probs = dict(all_probs)
    language = choose_dictation_language(probs, get_settings().dictation_detect_min_prob)
    top = max(probs, key=probs.get, default="?")
    logger.info(
        "Dictation language %s (detected %s p=%.3f, km=%.3f)",
        language, top, probs.get(top, 0.0), probs.get("km", 0.0),
    )
    return language


async def transcribe_clip(data: bytes, suffix: str, language: str | None) -> Transcript:
    """Transcribe a short dictation clip into plain text segments.

    @param language A language code, or None to detect it (see
           `choose_dictation_language`: any language, falling back to Khmer when
           detection is unsure, because Whisper misreads Khmer as its neighbours).
    """
    audio_path, duration = await extract_audio(data, suffix)
    try:
        limit = get_settings().dictation_max_seconds
        if duration and duration > limit:
            raise ValueError(f"Voice messages can be at most {int(limit)} seconds long")
        if language is None:
            language = await asyncio.to_thread(_detect_dictation_language, audio_path)
        transcript = await asyncio.to_thread(_transcribe_sync, audio_path, None, language)
    finally:
        audio_path.unlink(missing_ok=True)
    transcript.duration = duration or transcript.duration
    return transcript


def join_segments(segments: list[Segment], language: str) -> str:
    """Join dictation segments into one message.

    Khmer does not separate words with spaces, so joining its segments with a space
    would insert breaks mid-sentence; a Khmer segment boundary is a pause, not a word
    gap, and is joined directly.
    """
    parts = [s.text.strip() for s in segments if s.text.strip()]
    return ("" if language == "km" else " ").join(parts)

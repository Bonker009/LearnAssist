"""Audio extraction via FFmpeg."""

import asyncio
import logging
import shutil
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

# 16 kHz mono PCM is exactly what Whisper wants. Handing it anything else means
# the model resamples internally, which costs time and can lose quality.
FFMPEG_ARGS = ["-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", "-f", "wav"]


class FfmpegMissing(RuntimeError):
    pass


async def extract_audio(data: bytes, suffix: str = "") -> tuple[Path, float]:
    """Write `data` to a temp file and extract normalised audio from it.

    @return the path to the extracted WAV and its duration in seconds. The caller
            owns the file and must delete it.
    """
    if shutil.which("ffmpeg") is None:
        raise FfmpegMissing(
            "ffmpeg is not installed in this container. It is required to read "
            "audio and video uploads."
        )

    source = Path(tempfile.mkstemp(suffix=suffix or ".bin")[1])
    source.write_bytes(data)
    try:
        return await extract_audio_from_path(source)
    finally:
        source.unlink(missing_ok=True)


async def extract_audio_from_path(source: Path) -> tuple[Path, float]:
    """As `extract_audio`, for media already on disk (e.g. a downloaded video).

    The caller still owns `source`; only the returned WAV is created here.
    """
    if shutil.which("ffmpeg") is None:
        raise FfmpegMissing(
            "ffmpeg is not installed in this container. It is required to read "
            "audio and video uploads."
        )

    target = Path(tempfile.mkstemp(suffix=".wav")[1])
    try:
        process = await asyncio.create_subprocess_exec(
            "ffmpeg", "-nostdin", "-y", "-i", str(source), *FFMPEG_ARGS, str(target),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await process.communicate()
        if process.returncode != 0:
            target.unlink(missing_ok=True)
            # FFmpeg's diagnostics are long; the last lines carry the actual reason.
            tail = stderr.decode(errors="replace").strip().splitlines()[-3:]
            raise ValueError("Could not read this media file: " + " ".join(tail))

        return target, await probe_duration(target)
    except BaseException:
        target.unlink(missing_ok=True)
        raise


async def probe_duration(path: Path) -> float:
    """Duration in seconds, or 0.0 if it cannot be determined."""
    process = await asyncio.create_subprocess_exec(
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    stdout, _ = await process.communicate()
    try:
        return float(stdout.decode().strip())
    except (ValueError, AttributeError):
        return 0.0

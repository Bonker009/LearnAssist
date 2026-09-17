"""YouTube links: download the audio track, then transcribe like any recording.

The video itself is never stored. The citation viewer embeds the original, so a
"12:30" chip seeks the embedded player; only the audio is needed, and only for as
long as Whisper takes to read it.
"""

import asyncio
import logging
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from app.config import get_settings

logger = logging.getLogger(__name__)

# Must stay in step with YOUTUBE_HOSTS in the API's DocumentService.
YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be"}
_VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")


def youtube_video_id(url: str) -> str | None:
    """Extract the 11-character video id from any common YouTube URL shape."""
    parts = urlsplit(url.strip())
    host = (parts.hostname or "").lower()
    if host not in YOUTUBE_HOSTS:
        return None

    candidate: str | None = None
    segments = [s for s in parts.path.split("/") if s]
    if host == "youtu.be":
        candidate = segments[0] if segments else None
    elif parts.path == "/watch":
        candidate = parse_qs(parts.query).get("v", [None])[0]
    elif len(segments) >= 2 and segments[0] in ("shorts", "live", "embed", "v"):
        candidate = segments[1]

    return candidate if candidate and _VIDEO_ID.match(candidate) else None


@dataclass
class DownloadedAudio:
    path: Path
    title: str | None
    duration: float | None
    directory: Path

    def cleanup(self) -> None:
        shutil.rmtree(self.directory, ignore_errors=True)


def _download_sync(video_id: str) -> DownloadedAudio:
    import yt_dlp

    settings = get_settings()
    # Always fetch the canonical watch URL rebuilt from the id. Passing the student's
    # URL through would let yt-dlp's generic extractor fetch arbitrary hosts, and a
    # `list=` parameter would download a whole playlist.
    url = f"https://www.youtube.com/watch?v={video_id}"
    directory = Path(tempfile.mkdtemp(prefix="yt-"))

    options = {
        "format": "bestaudio/best",
        "outtmpl": str(directory / "%(id)s.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "allowed_extractors": ["youtube"],
        "max_filesize": 1024 * 1024 * 1024,
    }
    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=False)
            duration = info.get("duration")
            if info.get("is_live"):
                raise ValueError("Live streams can't be added. Add it once the stream has ended.")
            if duration and duration > settings.youtube_max_duration_seconds:
                hours = settings.youtube_max_duration_seconds // 3600
                raise ValueError(f"That video is longer than {hours} hours")

            info = ydl.process_ie_result(info, download=True)
            downloads = info.get("requested_downloads") or []
            path = Path(downloads[0]["filepath"]) if downloads else None
            if path is None or not path.exists():
                raise ValueError("Could not download the audio for that video")

            return DownloadedAudio(path, info.get("title"), duration, directory)
    except Exception:
        shutil.rmtree(directory, ignore_errors=True)
        raise


async def download_audio(url: str) -> DownloadedAudio:
    video_id = youtube_video_id(url)
    if video_id is None:
        raise ValueError("That doesn't look like a YouTube video link")
    try:
        return await asyncio.to_thread(_download_sync, video_id)
    except ValueError:
        raise
    except Exception as exc:  # noqa: BLE001 - yt-dlp raises its own DownloadError tree
        # yt-dlp messages are long and prefixed with "ERROR: [youtube] id:"; the useful
        # part ("Private video", "Video unavailable") is at the end.
        message = str(exc).split(":")[-1].strip() or "unknown error"
        raise ValueError(f"YouTube download failed: {message}") from exc

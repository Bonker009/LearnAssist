"""Links are fetched from inside the compose network, so they are an SSRF surface."""

import pytest

from app.fetch import UnsafeUrl, _split, is_public_address, resolve_public
from app.transcribe.youtube import youtube_video_id


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",
        "10.0.0.5",
        "172.18.0.3",  # a typical compose network address
        "192.168.1.10",
        "169.254.169.254",  # cloud metadata
        "100.64.0.1",  # CGNAT
        "0.0.0.0",
        "::1",
        "fd00::1",
        "::ffff:10.0.0.1",  # IPv4-mapped private address
        "224.0.0.1",
    ],
)
def test_private_and_special_addresses_are_refused(address):
    assert is_public_address(address) is False


@pytest.mark.parametrize("address", ["93.184.215.14", "2606:4700:4700::1111"])
def test_public_addresses_are_allowed(address):
    assert is_public_address(address) is True


@pytest.mark.parametrize("host", ["127.0.0.1", "[::1]", "10.1.2.3", "localhost"])
async def test_resolve_refuses_internal_hosts(host):
    with pytest.raises(UnsafeUrl):
        await resolve_public(host, 80)


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "gopher://example.com/",
        "ftp://example.com/x",
        "https://user:pass@example.com/",
        "https://example.com:99999/",
        "https:///nohost",
    ],
)
def test_malformed_or_non_http_urls_are_refused(url):
    with pytest.raises(UnsafeUrl):
        _split(url)


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtube.com/watch?v=dQw4w9WgXcQ&list=PL123&t=42s", "dQw4w9WgXcQ"),
        ("https://youtu.be/dQw4w9WgXcQ?si=abc", "dQw4w9WgXcQ"),
        ("https://m.youtube.com/shorts/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/live/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ],
)
def test_youtube_ids_are_extracted(url, expected):
    assert youtube_video_id(url) == expected


@pytest.mark.parametrize(
    "url",
    [
        "https://www.youtube.com/playlist?list=PL123",
        "https://www.youtube.com/watch?v=short",
        "https://evil.example/watch?v=dQw4w9WgXcQ",
        "https://youtube.com.evil.example/watch?v=dQw4w9WgXcQ",
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ/../../x",
    ],
)
def test_non_video_and_lookalike_links_are_refused(url):
    """Only a real video id is downloaded; the URL itself is never passed to yt-dlp."""
    assert youtube_video_id(url) is None

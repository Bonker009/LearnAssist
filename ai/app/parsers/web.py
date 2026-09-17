"""Web pages: fetched HTML -> main article text -> text units.

Extraction matters more than parsing here. A raw page is mostly navigation, cookie
banners and footers; embedding that would let a question about the article be
"answered" from the site's menu. trafilatura keeps the main content and its headings,
emitted as Markdown so the text parser can section it by heading.
"""

import logging
import re

from app.parsers.base import ParseResult
from app.parsers.text import decode_text, parse_text

logger = logging.getLogger(__name__)

_TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)


def page_title(html: str) -> str | None:
    match = _TITLE.search(html)
    if not match:
        return None
    import html as html_lib

    title = " ".join(html_lib.unescape(match.group(1)).split())
    return title[:300] or None


def extract_main_text(html: str, url: str | None = None) -> str:
    import trafilatura

    text = trafilatura.extract(
        html,
        url=url,
        output_format="markdown",
        include_comments=False,
        include_tables=True,
        include_links=False,
        include_images=False,
        # Recall over precision: a student added this page on purpose, so dropping a
        # real paragraph is worse than keeping a stray caption.
        favor_recall=True,
    )
    return text or ""


class WebParser:
    def __init__(self, url: str | None = None) -> None:
        self._url = url
        self.title: str | None = None

    def parse(self, data: bytes) -> ParseResult:
        html = decode_text(data)
        self.title = page_title(html)
        text = extract_main_text(html, self._url)
        if not text.strip():
            raise ValueError(
                "Could not find readable article text on that page. It may need "
                "JavaScript or a login to show its content."
            )
        logger.info("Extracted %d characters from %s", len(text), self._url or "page")
        return parse_text(text)

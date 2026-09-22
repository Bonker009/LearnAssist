"""Slide deck generation: a cited outline from the model, Slidev markdown from code.

The model never writes markdown. It returns a JSON outline whose slides cite
numbered blocks. Code validates the citations and renders the Slidev file, so a
slide cannot claim a source it was not given, and model text cannot inject markup:
Slidev compiles markdown into Vue templates, where `{{ ... }}` is evaluated and raw
HTML is rendered.
"""

import html
import json
import logging
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel

from app.llm.ollama import get_llm_provider
from app.models import Chunk, SourceRef
from app.quiz.generate import load_document_chunks
from app.quiz.sampling import stratified_sample

logger = logging.getLogger(__name__)

# Blocks offered per slide requested. Capped, and each block truncated, because an
# outline needs the gist of a section, and the whole prompt must fit the context.
BLOCKS_PER_SLIDE = 2
MAX_BLOCKS = 16
BLOCK_CHARS = 1500
MAX_BULLETS = 6

SLIDES_SYSTEM = """You turn lecture material into a short presentation outline.

Return JSON:
  {"title": "deck title",
   "slides": [{"title": "...", "bullets": ["...", "..."], "notes": "...",
               "source_markers": [1, 2]}]}

Rules:
1. Use ONLY what the numbered blocks say. Never add outside knowledge.
2. Each slide covers one idea: a title and 2 to 5 short bullets (under 20 words each).
3. "notes" is one to three sentences a presenter could say for that slide.
4. "source_markers" lists the blocks the slide was drawn from (at least one).
5. Follow the order of the blocks, so the deck follows the lecture.
6. Write in the language of the lecture material.
7. Plain text only: no markdown, HTML, emoji or numbering in titles or bullets."""


def build_slides_prompt(blocks: list[tuple[int, str, str]], count: int) -> str:
    rendered = "\n\n".join(f"[{marker}] ({label})\n{text}" for marker, label, text in blocks)
    return f"""Lecture material:

{rendered}

---
Write an outline of {count} slides. Return only the JSON object."""


class GeneratedSlide(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    bullets: list[str] = Field(default_factory=list)
    notes: str = Field(default="", max_length=1200)
    source_markers: list[int] = Field(default_factory=list)

    @field_validator("bullets")
    @classmethod
    def _clean_bullets(cls, bullets: list[str]) -> list[str]:
        cleaned = [" ".join(b.split()) for b in bullets if b and b.strip()]
        return [b[:240] for b in cleaned][:MAX_BULLETS]


class GeneratedOutline(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    slides: list[GeneratedSlide]


class _Camel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class SlideSource(_Camel):
    source: SourceRef
    source_label: str


class Slide(_Camel):
    title: str
    bullets: list[str]
    notes: str
    sources: list[SlideSource]


class SlideDeck(_Camel):
    """Returned to Spring: the cited outline it stores, and the file Slidev renders."""

    title: str
    slides: list[Slide]
    markdown: str


def validate_outline(outline: GeneratedOutline, blocks: dict[int, Chunk]) -> list[Slide]:
    """Keep slides with content and at least one real citation; drop unknown markers."""
    slides: list[Slide] = []
    for generated in outline.slides:
        markers = list(dict.fromkeys(m for m in generated.source_markers if m in blocks))
        if not markers or not generated.bullets:
            continue
        slides.append(
            Slide(
                title=" ".join(generated.title.split()),
                bullets=generated.bullets,
                notes=" ".join(generated.notes.split()),
                sources=[
                    SlideSource(source=blocks[m].source, source_label=blocks[m].source.label())
                    for m in markers
                ],
            )
        )
    return slides


def _text(value: str) -> str:
    """Inline text that Slidev shows literally.

    `v-pre` stops Vue evaluating `{{ }}` and directives. HTML-escaping stops tags.
    Markdown punctuation becomes numeric entities, which markdown-it decodes to plain
    characters after parsing, so `**`, `[x](y)`, `$x$` (KaTeX) and `|` cannot form
    markup.
    """
    escaped = html.escape(" ".join(value.split()), quote=False)
    escaped = "".join(f"&#{ord(c)};" if c in "\\`*_[](){}#+!|~$^=:" else c for c in escaped)
    return f'<span v-pre>{escaped}</span>'


def _notes(value: str) -> str:
    # Notes sit inside an HTML comment; escaping < and > means `-->` cannot close it.
    return html.escape(" ".join(value.split()), quote=False)


def render_slidev(title: str, subtitle: str, slides: list[Slide]) -> str:
    """Render a Slidev markdown file. Pure, so it is unit-tested directly."""
    headmatter = "\n".join(
        [
            "---",
            "theme: default",
            f"title: {json.dumps(title, ensure_ascii=False)}",
            # Hash routing lets the built deck work under any path the API serves it at.
            "routerMode: hash",
            "transition: slide-left",
            "mdc: false",
            "fonts:",
            "  sans: Inter, Kantumruy Pro",
            "layout: cover",
            "---",
        ]
    )
    parts = [f"{headmatter}\n\n# {_text(title)}\n\n{_text(subtitle)}\n"]

    for slide in slides:
        bullets = "\n".join(f"- {_text(b)}" for b in slide.bullets)
        labels = " · ".join(s.source_label for s in slide.sources)
        body = (
            f"# {_text(slide.title)}\n\n{bullets}\n\n"
            '<div class="absolute bottom-5 left-14 right-14 text-sm opacity-60">'
            f"Source: {_text(labels)}</div>\n"
        )
        if slide.notes:
            body += f"\n<!--\n{_notes(slide.notes)}\n-->\n"
        parts.append(body)

    return "\n---\n\n".join(parts)


async def generate_slides(document_id: UUID, filename: str, count: int = 8) -> SlideDeck | None:
    chunks = await load_document_chunks(document_id)
    if not chunks:
        return None

    sampled = stratified_sample(chunks, min(count * BLOCKS_PER_SLIDE, MAX_BLOCKS))
    blocks = dict(enumerate(sampled, start=1))
    rendered = [(m, c.source.label(), c.text[:BLOCK_CHARS]) for m, c in blocks.items()]

    outline = await get_llm_provider().complete_json(
        SLIDES_SYSTEM, build_slides_prompt(rendered, count), GeneratedOutline, temperature=0.3
    )
    slides = validate_outline(outline, blocks)[:count]
    if not slides:
        return None
    if len(slides) < len(outline.slides):
        logger.info("Kept %d of %d generated slides", len(slides), len(outline.slides))

    title = " ".join(outline.title.split())
    return SlideDeck(
        title=title,
        slides=slides,
        markdown=render_slidev(title, filename, slides),
    )

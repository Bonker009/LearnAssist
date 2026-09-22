"""Flashcard and slide validation, and the Slidev renderer's escaping.

The model's output is untrusted twice over here: a card or slide citing a block it
was never given must be dropped, and slide text must never become markup, because
Slidev compiles markdown into Vue templates that run in the student's browser.
"""

from uuid import uuid4

import pytest

from app.models import Chunk, SourceRef
from app.study.flashcards import GeneratedCard, validate_cards
from app.study.slides import (
    GeneratedOutline,
    GeneratedSlide,
    Slide,
    SlideSource,
    render_slidev,
    validate_outline,
)

DOC = uuid4()


def _blocks(count: int = 3) -> dict[int, Chunk]:
    return {
        i: Chunk(
            document_id=DOC,
            ordinal=i,
            text=f"Block {i} text about photosynthesis.",
            source=SourceRef(kind="page", page_no=i + 3),
        )
        for i in range(1, count + 1)
    }


# ---------- flashcards ----------


def test_card_is_bound_to_the_block_it_cites():
    cards = validate_cards(
        [GeneratedCard(front="Chloroplast", back="Where photosynthesis happens.", source_marker=2)],
        _blocks(),
    )
    assert len(cards) == 1
    assert cards[0].source.page_no == 5
    assert cards[0].source_label == "Page 5"
    assert "Block 2" in cards[0].snippet


def test_card_citing_unknown_block_is_dropped():
    cards = validate_cards(
        [GeneratedCard(front="Stroma", back="Fluid of the chloroplast.", source_marker=9)],
        _blocks(),
    )
    assert cards == []


def test_repeated_fronts_are_dropped_case_insensitively():
    generated = [
        GeneratedCard(front="Calvin  cycle", back="Fixes CO2.", source_marker=1),
        GeneratedCard(front="calvin cycle", back="Also fixes CO2.", source_marker=2),
    ]
    cards = validate_cards(generated, _blocks())
    assert [c.front for c in cards] == ["Calvin cycle"]


def test_flashcards_serialise_camel_case_for_spring():
    card = validate_cards(
        [GeneratedCard(front="Term", back="Meaning", source_marker=1)], _blocks()
    )[0]
    dumped = card.model_dump(by_alias=True)
    assert "sourceLabel" in dumped
    # The nested SourceRef keeps snake_case: the browser's types expect page_no.
    assert "page_no" in dumped["source"]


# ---------- slide outline ----------


def _outline(*slides: GeneratedSlide) -> GeneratedOutline:
    return GeneratedOutline(title="Photosynthesis", slides=list(slides))


def test_slide_keeps_only_known_markers_in_order():
    slides = validate_outline(
        _outline(GeneratedSlide(title="Light", bullets=["a"], source_markers=[3, 9, 1, 3])),
        _blocks(),
    )
    assert [s.source_label for s in slides[0].sources] == ["Page 6", "Page 4"]


def test_slide_without_a_real_citation_is_dropped():
    slides = validate_outline(
        _outline(
            GeneratedSlide(title="Invented", bullets=["x"], source_markers=[7]),
            GeneratedSlide(title="Uncited", bullets=["x"], source_markers=[]),
            GeneratedSlide(title="Empty", bullets=[], source_markers=[1]),
        ),
        _blocks(),
    )
    assert slides == []


def test_bullets_are_trimmed_and_capped():
    slide = GeneratedSlide(title="t", bullets=["  a  b ", "", *["x"] * 10], source_markers=[1])
    assert slide.bullets[0] == "a b"
    assert len(slide.bullets) == 6


# ---------- Slidev rendering ----------


def _slide(title="Light reactions", bullets=("Occur in the thylakoid",), notes="") -> Slide:
    return Slide(
        title=title,
        bullets=list(bullets),
        notes=notes,
        sources=[SlideSource(source=SourceRef(kind="page", page_no=4), source_label="Page 4")],
    )


def test_deck_has_headmatter_cover_and_one_section_per_slide():
    markdown = render_slidev("Photosynthesis", "lecture.pdf", [_slide(), _slide()])
    assert markdown.startswith("---\ntheme: default\n")
    assert "routerMode: hash" in markdown
    assert "layout: cover" in markdown
    # Headmatter fences + cover + two slide separators.
    assert markdown.count("\n---\n") == 3
    assert markdown.count("Source: ") == 2


def test_every_slide_cites_its_source():
    markdown = render_slidev("T", "f", [_slide()])
    assert "Source: <span v-pre>Page 4</span>" in markdown


@pytest.mark.parametrize(
    "hostile",
    [
        "{{ $slidev.nav.next() }}",
        "<img src=x onerror=alert(1)>",
        "<script>alert(1)</script>",
        "[click](javascript:alert(1))",
        "**bold** $x^2$ | table",
    ],
)
def test_model_text_cannot_become_markup(hostile):
    markdown = render_slidev(hostile, hostile, [_slide(title=hostile, bullets=[hostile])])
    body = markdown.split("---", 2)[2]  # skip the headmatter, where the title is YAML
    assert "{{" not in body
    assert "<img" not in body and "<script" not in body
    assert "](" not in body and "**" not in body and "$" not in body


def test_title_is_valid_yaml_even_with_quotes():
    markdown = render_slidev('He said "hi": ok', "f", [_slide()])
    assert 'title: "He said \\"hi\\": ok"' in markdown


def test_notes_cannot_close_the_comment():
    markdown = render_slidev("T", "f", [_slide(notes="end --> <b>x</b>")])
    assert "end --&gt; &lt;b&gt;x&lt;/b&gt;" in markdown


def test_slide_separator_cannot_be_injected():
    markdown = render_slidev("T", "f", [_slide(bullets=["a\n---\nlayout: cover"])])
    assert markdown.count("\n---\n") == 2

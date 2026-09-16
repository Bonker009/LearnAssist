"""SourceRef must not be constructible in an ambiguous state."""

import pytest
from pydantic import ValidationError

from app.models import SourceRef


def test_slide_requires_slide_number():
    with pytest.raises(ValidationError):
        SourceRef(kind="slide")


def test_page_requires_page_number():
    with pytest.raises(ValidationError):
        SourceRef(kind="page")


def test_timestamp_requires_start():
    with pytest.raises(ValidationError):
        SourceRef(kind="timestamp")


@pytest.mark.parametrize(
    ("ref", "expected"),
    [
        (SourceRef(kind="slide", slide_no=12), "Slide 12"),
        (SourceRef(kind="page", page_no=3), "Page 3"),
        (SourceRef(kind="timestamp", start_sec=0.0), "0:00"),
        (SourceRef(kind="timestamp", start_sec=65.4), "1:05"),
        (SourceRef(kind="timestamp", start_sec=3725.0), "62:05"),
    ],
)
def test_labels(ref, expected):
    assert ref.label() == expected

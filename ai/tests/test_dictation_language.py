"""Voice messages: any language, with Khmer as the fallback when detection is unsure.

The probabilities are what Whisper `small` reported for short synthesised questions.
It never ranks Khmer speech confidently (it guesses Vietnamese, Thai or English),
which is why an unsure detection must become Khmer rather than the wrong language.
"""

import pytest

from app.transcribe.whisper import choose_dictation_language

MIN_PROB = 0.9


@pytest.mark.parametrize(
    ("probs", "expected"),
    [
        # Khmer speech, as Whisper actually scored it.
        ({"vi": 0.539, "km": 0.370, "en": 0.021}, "km"),
        ({"th": 0.865, "km": 0.047, "en": 0.005}, "km"),
        ({"en": 0.319, "cy": 0.127, "km": 0.018}, "km"),  # a single word, 1.9 s
        ({"km": 0.896, "th": 0.05}, "km"),
        ({"km": 0.300, "th": 0.25, "vi": 0.2}, "km"),
        # Other languages are detected confidently and kept.
        ({"en": 0.999, "km": 0.0}, "en"),
        ({"th": 0.921, "km": 0.004}, "th"),
        ({"vi": 0.986, "km": 0.001}, "vi"),
        ({"fr": 0.995}, "fr"),
        ({"zh": 1.0}, "zh"),
    ],
)
def test_choose_dictation_language(probs, expected):
    assert choose_dictation_language(probs, MIN_PROB) == expected


def test_no_probabilities_falls_back_to_khmer():
    assert choose_dictation_language({}, MIN_PROB) == "km"

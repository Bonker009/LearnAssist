"""Language detection for replies.

Only the one distinction the product acts on is detected: whether the student wrote
in Khmer. That is decidable from the script alone -- Khmer has its own Unicode block
-- so no language-identification model is needed, and short, typo-ridden questions
are classified as reliably as long ones.
"""

import re
from typing import Literal

Language = Literal["km", "other"]

# Khmer (U+1780-U+17FF) and Khmer Symbols (U+19E0-U+19FF).
_KHMER = re.compile(r"[\u1780-\u17FF\u19E0-\u19FF]")
_LETTER = re.compile(r"[^\W\d_]", re.UNICODE)

# A question is Khmer when Khmer characters are a substantial share of its letters.
# Not a majority: "RuBisCO ធ្វើអ្វី?" is a Khmer question about an English term, and
# counting letters would call it English because Latin letters are one code point
# each while a Khmer syllable is often several.
_KHMER_SHARE = 0.3


def detect_language(text: str) -> Language:
    # Every Khmer code point counts, including vowel signs and COENG, which are not
    # "letters" to the regex engine; other scripts are counted by letter.
    khmer = len(_KHMER.findall(text))
    other = sum(1 for c in _LETTER.findall(text) if not _KHMER.match(c))
    if khmer + other == 0:
        return "other"
    return "km" if khmer / (khmer + other) >= _KHMER_SHARE else "other"


def is_khmer(text: str) -> bool:
    return detect_language(text) == "km"

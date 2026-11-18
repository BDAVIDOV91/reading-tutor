"""Mark one final attempt at one text word (ADR 0001 unsure rule; tests/cases/README.md)."""

from __future__ import annotations

from enum import StrEnum

from reading_tutor.core.similarity import similarity

UNSURE_THRESHOLD = 0.80  # untuned starting value (ADR 0001)
SHORT_WORD_MAX = 4  # expected words of this many letters or fewer must match exactly
_EPS = 1e-9  # 1 - 1/5 must count as 0.80

# A heard digit (or digit + article) is correct when the text word is in its set. Ordinals are left out.
DIGIT_WORDS: dict[str, frozenset[str]] = {
    k: frozenset(v)
    for k, v in {
        "0": {"нула"},
        "1": {"един", "една", "едно", "едни"},
        "2": {"два", "две", "двама"},
        "3": {"три", "трима"},
        "4": {"четири", "четирима"},
        "5": {"пет", "петима"},
        "6": {"шест", "шестима"},
        "7": {"седем", "седмина"},
        "8": {"осем", "осмина"},
        "9": {"девет", "деветима"},
        "10": {"десет", "десетима"},
        "2те": {"двете"},
        "2та": {"двата"},
        "2мата": {"двамата"},
        "3те": {"трите"},
        "3мата": {"тримата"},
        "4те": {"четирите"},
        "5те": {"петте"},
        "6те": {"шестте"},
        "7те": {"седемте"},
        "8те": {"осемте"},
        "9те": {"деветте"},
        "10те": {"десетте"},
    }.items()
}

# Full and short definite article sound the same; only the spelling differs (owner 2026-11-18).
_ARTICLE_PAIRS = (("ът", "а"), ("ят", "я"))
_MIN_STEM = 3


class Mark(StrEnum):
    CORRECT = "correct"
    MISREAD = "misread"
    SKIPPED = "skipped"
    UNSURE = "unsure"
    NOT_ATTEMPTED = "not_attempted"


def _article_stem(word: str) -> set[tuple[str, int]]:
    """(stem, pair index) for every article ending the word could carry."""
    out: set[tuple[str, int]] = set()
    for i, pair in enumerate(_ARTICLE_PAIRS):
        for ending in pair:
            stem = word[: -len(ending)]
            if word.endswith(ending) and len(stem) >= _MIN_STEM:
                out.add((stem, i))
    return out


def equivalent(expected: str, heard: str) -> bool:
    """Exact match, digit lookup, or full/short article of the same stem. Inputs are normalised."""
    if expected == heard:
        return True
    if expected in DIGIT_WORDS.get(heard, ()):
        return True
    return bool(_article_stem(expected) & _article_stem(heard))


def judge(expected: str, heard: str) -> Mark:
    if equivalent(expected, heard):
        return Mark.CORRECT
    if len(expected) <= SHORT_WORD_MAX:
        return Mark.MISREAD
    if similarity(expected, heard) >= UNSURE_THRESHOLD - _EPS:
        return Mark.UNSURE
    return Mark.MISREAD

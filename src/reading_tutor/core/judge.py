"""Mark one final attempt at one text word (ADR 0001 unsure rule; rule 17 vowel reduction; tests/cases/README.md)."""

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

# Rule 17 (owner 2026-11-19): unstressed о is heard as у and а as ъ (and back). Sources: Sabev et al.,
# Interspeech 2023 (о/у merge); Andreeva et al. 2013 (а/ъ, debated). е/и and я/е are left out: пие/пее is a
# real minimal pair. There is no stress dictionary, so at least one vowel letter must stay unchanged.
REDUCTION_PAIRS = frozenset({("о", "у"), ("у", "о"), ("а", "ъ"), ("ъ", "а")})
VOWELS = frozenset("аеиоуъюя")  # ю and я count as vowels but are never a covered position

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


def _is_reduction(expected: str, heard: str) -> bool:
    """Rule 17: same length, compared letter by letter (Hamming); every differing position is an о/у or а/ъ
    pair; 1 to (vowel letters - 1) positions differ. Stress is not checked, so a changed stressed vowel can be
    accepted (known limit, tests/cases/README.md)."""
    if len(expected) != len(heard):
        return False
    vowels = sum(ch in VOWELS for ch in expected)
    diffs = [(a, b) for a, b in zip(expected, heard, strict=True) if a != b]
    return 1 <= len(diffs) <= vowels - 1 and all(d in REDUCTION_PAIRS for d in diffs)


def judge_detail(expected: str, heard: str) -> tuple[Mark, str]:
    """The mark and the rule that decided it ("reduction" or "")."""
    if equivalent(expected, heard):
        return Mark.CORRECT, ""
    if _is_reduction(expected, heard):
        return Mark.CORRECT, "reduction"
    if len(expected) <= SHORT_WORD_MAX:
        return Mark.MISREAD, ""
    if similarity(expected, heard) >= UNSURE_THRESHOLD - _EPS:
        return Mark.UNSURE, ""
    return Mark.MISREAD, ""


def judge(expected: str, heard: str) -> Mark:
    return judge_detail(expected, heard)[0]

"""Text normalisation and tokenisation for Bulgarian reading text and engine transcripts.

Rules: tests/cases/README.md (owner-approved 2026-11-18).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Literal

Side = Literal["text", "heard"]

# Stress marks only. U+0306 (breve, as in й) is a letter part and is kept.
_STRESS_MARKS = {"̀", "́"}

# Case-sensitive Latin look-alikes, applied before casefold and only inside tokens that also contain Cyrillic.
_LOOKALIKES = str.maketrans(
    {
        "A": "А", "B": "В", "C": "С", "E": "Е", "H": "Н", "K": "К", "M": "М", "O": "О", "P": "Р", "T": "Т",
        "X": "Х", "Y": "У",
        "a": "а", "c": "с", "e": "е", "o": "о", "p": "р", "x": "х", "y": "у", "k": "к",
    }
)  # fmt: skip

# Hyphens join word parts on the text side ("ма-ма" is one word); every dash splits on the heard side.
_HYPHENS = "-‐‑"
_OTHER_DASHES = "‒–—―−﹘﹣－"
_SPLIT = {
    "text": re.compile(f"[{re.escape(_OTHER_DASHES)}]"),
    "heard": re.compile(f"[{re.escape(_HYPHENS + _OTHER_DASHES)}]"),
}
_JOIN_TEXT = re.compile(f"[{re.escape(_HYPHENS)}]")
# Heard "2-те" / "2-та" / "2-мата" stays one token for the digit lookup.
_DIGIT_ARTICLE = re.compile(f"(\\d+)[{re.escape(_HYPHENS + _OTHER_DASHES)}](те|та|мата)(?=\\W|$)", re.IGNORECASE)
_DIGIT_ARTICLE_MARK = "\u0000"


@dataclass(frozen=True)
class Token:
    norm: str
    surface: str


def _is_cyrillic(ch: str) -> bool:
    return "Ѐ" <= ch <= "ӿ"


def _is_latin(ch: str) -> bool:
    return ch.isascii() and ch.isalpha()


def normalise_token(raw: str) -> str:
    """One token to its comparison form: no stress marks, look-alikes fixed, casefolded, letters and digits only."""
    decomposed = unicodedata.normalize("NFD", raw)
    text = unicodedata.normalize("NFC", "".join(ch for ch in decomposed if ch not in _STRESS_MARKS))
    if any(_is_cyrillic(ch) for ch in text) and any(_is_latin(ch) for ch in text):
        text = text.translate(_LOOKALIKES)
    text = text.casefold()
    return "".join(ch for ch in text if ch.isalpha() or ch.isdecimal())


def tokenise(text: str, *, side: Side) -> list[Token]:
    """Split into tokens, keeping each token's original surface form; drop tokens that normalise to nothing."""
    tokens: list[Token] = []
    for chunk in text.split():
        if side == "heard":
            chunk = _DIGIT_ARTICLE.sub(lambda m: f"{m[1]}{_DIGIT_ARTICLE_MARK}{m[2]}", chunk)
        for part in _SPLIT[side].split(chunk):
            surface = part.replace(_DIGIT_ARTICLE_MARK, "-")
            norm = normalise_token(_JOIN_TEXT.sub("", part) if side == "text" else part)
            if norm:
                tokens.append(Token(norm=norm, surface=surface))
    return tokens

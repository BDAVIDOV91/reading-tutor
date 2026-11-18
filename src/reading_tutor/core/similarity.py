"""The one swappable similarity function (plan Q5): rapidfuzz normalised Levenshtein, 1 - distance / max length."""

from __future__ import annotations

from rapidfuzz.distance import Levenshtein

SIMILARITY_FN = "rapidfuzz.Levenshtein.normalized_similarity"


def similarity(a: str, b: str) -> float:
    return Levenshtein.normalized_similarity(a, b)

"""Core: normalise, judge, align, score. Pure functions; no UI, network, engine or browser imports (R11).

The rules are defined by the language-neutral case files in tests/cases/ (see tests/cases/README.md).
"""

from reading_tutor.core.align import WordMark, align
from reading_tutor.core.judge import Mark, judge
from reading_tutor.core.normalise import Token, normalise_token, tokenise
from reading_tutor.core.score import Score, score
from reading_tutor.core.similarity import similarity

CORE_VERSION = "0.1.0"

__all__ = [
    "CORE_VERSION",
    "Mark",
    "Score",
    "Token",
    "WordMark",
    "align",
    "judge",
    "normalise_token",
    "score",
    "similarity",
    "tokenise",
]

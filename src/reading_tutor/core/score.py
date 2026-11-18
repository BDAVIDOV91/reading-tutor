"""Per-attempt figures from the word marks and the recording duration (ADR 0001 metrics; plan Q7).

Variant C counts unsure as correct, variant F counts it as flagged. not_attempted words are left out of every
figure; skipped words count as attempted and not correct. Fractions and rates are rounded to 2 decimals.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TypedDict

from reading_tutor.core.judge import Mark

_VALID = {m.value for m in Mark}


class Score(TypedDict):
    attempted: int
    correct_C: int
    correct_F: int
    accuracy_C: float | None
    accuracy_F: float | None
    wcpm_C: float | None
    wcpm_F: float | None
    raw_wpm: float | None
    unsure_per_100: float | None


def _ratio(n: float, d: float) -> float | None:
    return round(n / d, 2) if d else None


def score(marks: Sequence[str], duration_s: float) -> Score:
    unknown = set(marks) - _VALID
    if unknown:
        raise ValueError(f"unknown marks: {sorted(unknown)}")
    if duration_s < 0:
        raise ValueError("duration_s must be >= 0")

    attempted = sum(m != Mark.NOT_ATTEMPTED for m in marks)
    correct_f = sum(m == Mark.CORRECT for m in marks)
    unsure = sum(m == Mark.UNSURE for m in marks)
    correct_c = correct_f + unsure

    def per_minute(n: int) -> float | None:
        if duration_s == 0:
            return None if attempted else 0.0
        return round(n * 60 / duration_s, 2)

    return Score(
        attempted=attempted,
        correct_C=correct_c,
        correct_F=correct_f,
        accuracy_C=_ratio(correct_c, attempted),
        accuracy_F=_ratio(correct_f, attempted),
        wcpm_C=per_minute(correct_c),
        wcpm_F=per_minute(correct_f),
        raw_wpm=per_minute(attempted),
        unsure_per_100=_ratio(100 * unsure, attempted),
    )

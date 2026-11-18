"""Core modules together: text + transcript -> marks -> score, on an invented graded passage.

Integration layer for step 1 (no engine, no storage yet). Later steps add SQLite log and local-engine runs on
adult fixtures here.
"""

from __future__ import annotations

import pytest

from reading_tutor.core import CORE_VERSION, align, score

pytestmark = pytest.mark.integration

TEXT = (
    "Ма-ма и Ани оти-доха в гра-дината. Слънцето грееше силно. "
    "Ани видя две пеперуди и една котка. Котката спеше под дървото."
)
# A slow reader: syllables, a repeat, a self-correction, a skipped word, a near miss, a misread and an early stop.
HEARD = "ма ма и ани оти до ха в градината слънцето грееше грееше сил но ани видя 2 пеперуди и една кошка котка котката спаше"


def test_slow_reader_end_to_end():
    marks = align(TEXT, HEARD)
    by_word = [(m.word, str(m.mark)) for m in marks]
    assert by_word == [
        ("мама", "correct"),
        ("и", "correct"),
        ("ани", "correct"),
        ("отидоха", "correct"),
        ("в", "correct"),
        ("градината", "correct"),
        ("слънцето", "correct"),
        ("грееше", "correct"),
        ("силно", "correct"),
        ("ани", "correct"),
        ("видя", "correct"),
        ("две", "correct"),
        ("пеперуди", "correct"),
        ("и", "correct"),
        ("една", "correct"),
        ("котка", "correct"),
        ("котката", "correct"),
        ("спеше", "unsure"),
        ("под", "not_attempted"),
        ("дървото", "not_attempted"),
    ]

    s = score([str(m.mark) for m in marks], duration_s=36)
    assert s["attempted"] == 18
    assert s["correct_F"] == 17 and s["correct_C"] == 18
    assert s["accuracy_F"] == 0.94 and s["accuracy_C"] == 1.0
    assert s["raw_wpm"] == 30.0
    assert CORE_VERSION


def test_child_who_stops_after_a_skip_and_misread():
    marks = align("Кучето лае. Котката спи на стола.", "кучето лай котката стола")
    assert [str(m.mark) for m in marks] == ["correct", "misread", "correct", "skipped", "skipped", "correct"]
    s = score([str(m.mark) for m in marks], duration_s=12)
    assert s == {
        "attempted": 6,
        "correct_C": 3,
        "correct_F": 3,
        "accuracy_C": 0.5,
        "accuracy_F": 0.5,
        "wcpm_C": 15.0,
        "wcpm_F": 15.0,
        "raw_wpm": 30.0,
        "unsure_per_100": 0.0,
    }

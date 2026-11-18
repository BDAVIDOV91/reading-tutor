"""Properties that hold for any input, not just the case files."""

from __future__ import annotations

import random
import time

import pytest

from reading_tutor.core.align import align
from reading_tutor.core.judge import Mark
from reading_tutor.core.normalise import tokenise

pytestmark = pytest.mark.unit

WORDS = "мама татко котка куче мие ръце има баба дом слънце грее ябълка две 2 ко те то ъъъ".split()


def _random_text(rng: random.Random, n: int) -> str:
    return " ".join(rng.choice(WORDS) for _ in range(n))


@pytest.mark.parametrize("seed", range(40))
def test_one_mark_per_text_word_and_marks_are_consistent(seed: int):
    rng = random.Random(seed)
    text = _random_text(rng, rng.randint(0, 15))
    heard = _random_text(rng, rng.randint(0, 20))
    marks = align(text, heard)
    assert [m.word for m in marks] == [t.norm for t in tokenise(text, side="text")]
    for m in marks:
        assert (m.heard is None) == (m.mark in (Mark.SKIPPED, Mark.NOT_ATTEMPTED))
    # not_attempted only after the last word reached
    states = [m.mark for m in marks]
    if Mark.NOT_ATTEMPTED in states:
        first = states.index(Mark.NOT_ATTEMPTED)
        assert all(s == Mark.NOT_ATTEMPTED for s in states[first:])


def test_identical_reading_is_all_correct():
    text = "Мама има котка. Котката спи на топлото легло, а кучето лае."
    assert {m.mark for m in align(text, text)} == {Mark.CORRECT}


def test_two_minute_read_aligns_quickly():
    rng = random.Random(7)
    text = _random_text(rng, 150)
    heard = _random_text(rng, 190)  # a messy read: nothing lines up well
    start = time.perf_counter()
    marks = align(text, heard)
    assert len(marks) == 150
    assert time.perf_counter() - start < 3.0

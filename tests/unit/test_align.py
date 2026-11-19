from __future__ import annotations

import pytest
from casefiles import case_params

from reading_tutor.core.align import align

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("case", case_params("align"))
def test_align(case):
    got = [{"word": w.word, "mark": str(w.mark), "heard": w.heard} for w in align(case["text"], case["heard"])]
    assert got == case["expected"], case["note"]


def test_align_keeps_text_surface_forms():
    marks = align("Ма-ма чете.", "мама чете")
    assert [m.surface for m in marks] == ["Ма-ма", "чете."]


def test_align_empty_text_gives_no_marks():
    assert align("", "мама") == []


def test_word_mark_via_names_the_rule_that_decided_the_mark():
    """Rules 17 and 18 (2026-11-19): `via` is core-only (not logged), so the engine eval can count their marks."""
    assert [m.via for m in align("Коза пасе.", "куза пасе")] == ["reduction", ""]
    assert [m.via for m in align("Мила пее.", "милапее")] == ["glue", "glue"]
    assert [m.via for m in align("Мила пее.", "милапе")] == ["glue", "glue"]
    assert [m.via for m in align("Мила пее.", "мила пее")] == ["", ""]

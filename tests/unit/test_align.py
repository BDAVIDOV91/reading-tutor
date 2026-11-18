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

from __future__ import annotations

import pytest
from casefiles import case_params

from reading_tutor.core.judge import judge
from reading_tutor.core.similarity import similarity

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("case", case_params("judge"))
def test_judge(case):
    assert judge(case["expected"], case["heard"]) == case["mark"], case["note"]


def test_similarity_is_rapidfuzz_normalized_levenshtein():
    assert similarity("котка", "котка") == 1.0
    assert similarity("котка", "кошка") == pytest.approx(0.8)
    assert similarity("рисува", "пише") == pytest.approx(1 - 5 / 6)
    assert similarity("", "") == 1.0

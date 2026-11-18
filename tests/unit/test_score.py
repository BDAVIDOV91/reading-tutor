from __future__ import annotations

import pytest
from casefiles import case_params

from reading_tutor.core.score import score

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("case", case_params("score"))
def test_score(case):
    assert dict(score(case["marks"], case["duration_s"])) == case["expected"], case["note"]


def test_score_rejects_unknown_mark():
    with pytest.raises(ValueError):
        score(["correct", "great"], 10)


def test_score_rejects_negative_duration():
    with pytest.raises(ValueError):
        score(["correct"], -1)

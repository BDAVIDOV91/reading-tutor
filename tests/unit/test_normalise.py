from __future__ import annotations

import pytest
from casefiles import case_params

from reading_tutor.core.normalise import normalise_token, tokenise

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("case", case_params("normalise", "token_cases"))
def test_normalise_token(case):
    assert normalise_token(case["input"]) == case["expected"], case["note"]


@pytest.mark.parametrize("case", case_params("normalise", "tokenise_cases"))
def test_tokenise(case):
    tokens = tokenise(case["input"], side=case["side"])
    assert [t.norm for t in tokens] == case["expected_tokens"], case["note"]
    assert [t.surface for t in tokens] == case["expected_surface"], case["note"]

"""Shared test helpers.

Test layers (mirrors pdf_data_extractor_v2's unit / integration / e2e groups):
  tests/unit/         pytestmark = pytest.mark.unit
  tests/integration/  pytestmark = pytest.mark.integration
  tests/e2e/          pytestmark = pytest.mark.e2e
tests/unit/test_layer_guard.py fails if a test module has no layer marker or the wrong one.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

CASES_DIR = Path(__file__).parent / "cases"


def load_cases(behaviour: str, key: str = "cases") -> list[dict]:
    data = json.loads((CASES_DIR / f"{behaviour}.json").read_text(encoding="utf-8"))
    assert data["behaviour"] == behaviour
    return data[key]


def case_params(behaviour: str, key: str = "cases") -> list:
    return [pytest.param(c, id=c["id"]) for c in load_cases(behaviour, key)]

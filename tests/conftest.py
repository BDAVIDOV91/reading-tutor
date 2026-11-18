"""Session-wide guards.

Every test runs with READING_TUTOR_DATA_DIR pointing into its own tmp_path, so nothing a test writes can land in
the repo's data/ (child data). A test that points it back at data/ fails (step 2 plan, privacy section).
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
REAL_DATA = (REPO / "data").resolve()


def points_at_real_data(value: str | None) -> bool:
    if not value:
        return False
    p = Path(value).resolve()
    return p == REAL_DATA or p.is_relative_to(REAL_DATA)


@pytest.fixture(autouse=True)
def _isolated_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    data = tmp_path / "data"
    monkeypatch.setenv("READING_TUTOR_DATA_DIR", str(data))
    monkeypatch.delenv("READING_TUTOR_CHILD_RECORDING", raising=False)
    monkeypatch.delenv("READING_TUTOR_FAKE_ENGINE", raising=False)
    assert not points_at_real_data(str(data)), "tmp_path resolved into the repo's data/"
    yield data
    assert not points_at_real_data(os.environ.get("READING_TUTOR_DATA_DIR")), (
        "a test pointed READING_TUTOR_DATA_DIR at the repo's data/ (child data); use tmp_path"
    )

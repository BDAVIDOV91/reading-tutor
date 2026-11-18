"""Settings (privacy review 2026-11-18, finding 9): a data dir inside the repo must be the gitignored data/."""

from __future__ import annotations

from pathlib import Path

import pytest

from reading_tutor import settings

pytestmark = pytest.mark.unit

REPO = Path(settings.__file__).resolve().parents[2]


def test_data_dir_inside_repo_but_not_data_is_refused(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("READING_TUTOR_DATA_DIR", str(REPO / "src" / "oops"))
    with pytest.raises(ValueError, match="data"):
        settings.load_settings()


def test_data_dir_outside_repo_is_allowed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("READING_TUTOR_DATA_DIR", str(tmp_path / "d"))
    assert settings.load_settings().data_dir == tmp_path / "d"


def test_default_is_repo_data(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("READING_TUTOR_DATA_DIR")
    assert settings.load_settings().data_dir == REPO / "data"

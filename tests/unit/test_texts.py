"""Built-in texts (texts/*.json): every one loads, tokenises non-empty, and has a stable version hash."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from reading_tutor.core import tokenise
from reading_tutor.texts import TEXTS_DIR, Text, load_builtin, pasted_text_id, text_version_hash

pytestmark = pytest.mark.unit

FILES = sorted(TEXTS_DIR.glob("*.json"))


def test_six_texts_ship():
    assert {p.stem for p in FILES} >= {
        "t1-mila-pee", "t2-moyat-dom", "t3-pastra-kotka", "t4-palachinki", "t5-patitsite-v-parka",
        "p1-vazov-az-sam-bylgarche",
    }  # fmt: skip


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.stem)
def test_text_file_is_complete(path: Path):
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert set(raw) == {"id", "level", "title", "text", "source", "licence"}
    assert raw["id"] == path.stem
    assert raw["licence"]
    assert raw["source"]
    assert tokenise(raw["text"], side="text")


def test_load_builtin_returns_texts_by_id():
    texts = load_builtin()
    t1 = texts["t1-mila-pee"]
    assert isinstance(t1, Text)
    assert t1.level == 1
    assert [t.level for t in sorted(texts.values(), key=lambda t: t.id) if t.id.startswith("t")] == [1, 2, 3, 4, 5]


def test_version_hash_is_stable_and_ignores_case_and_punctuation():
    a = text_version_hash("Мама мие. Тато чете!")
    assert a == text_version_hash("мама  мие тато ЧЕТЕ")
    assert a != text_version_hash("Мама мие. Тато пише!")
    assert len(a) == 16


def test_version_hash_pinned():
    """Pinned: a change here means every logged attempt's text_version_hash changes meaning."""
    assert text_version_hash("Мама мие.") == text_version_hash("мама мие")
    assert text_version_hash("Мама мие.") == PINNED


PINNED = "e35a56a1751b7156"  # sha256("мама\nмие")[:16], checked with sha256sum


def test_loader_refuses_mismatched_id(tmp_path: Path):
    (tmp_path / "x.json").write_text(
        json.dumps({"id": "y", "level": 1, "title": "T", "text": "мама", "source": "s", "licence": "l"}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="id"):
        load_builtin(tmp_path)


def test_loader_refuses_empty_text(tmp_path: Path):
    (tmp_path / "x.json").write_text(
        json.dumps({"id": "x", "level": 1, "title": "T", "text": " — ", "source": "s", "licence": "l"}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="no words"):
        load_builtin(tmp_path)


def test_pasted_text_id_is_derived_from_the_hash_and_never_collides_with_builtin():
    pid = pasted_text_id("Котката спи.")
    assert pid.startswith("u-")
    assert pid == pasted_text_id("котката  спи")
    assert pid not in load_builtin()

"""Adult audio fixture sidecars (tests/fixtures/sidecars/*.json, committed; the WAVs stay local).

Checks the schema, and that the expected marks agree with align(text, reference_transcript): this scores the
aligner on hand-written transcripts with no engine involved (engine-evaluator requirement).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from reading_tutor.core import align
from reading_tutor.texts import load_builtin

pytestmark = pytest.mark.unit

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
SIDECARS = sorted((FIXTURES / "sidecars").glob("*.json"))
MANIFEST = FIXTURES / "FIXTURES.md"
KINDS = {"clean", "syllables", "misreads_skip", "repeats_selfcorrection"}
FIELDS = {
    "id", "text_id", "kind", "speaker", "recorded_by", "device", "audio", "instructions", "planned",
    "reference_transcript", "expected_marks",
}  # fmt: skip
MARKS = {"correct", "misread", "skipped", "unsure", "not_attempted"}


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_first_set_is_eight_clips_two_texts_four_kinds():
    data = [_load(p) for p in SIDECARS]
    assert len(data) == 8
    pairs = {(d["text_id"], d["kind"]) for d in data}
    assert pairs == {(t, k) for t in ("t1-mila-pee", "t5-patitsite-v-parka") for k in KINDS}


@pytest.mark.parametrize("path", SIDECARS, ids=lambda p: p.stem)
def test_sidecar_schema(path: Path):
    d = _load(path)
    assert set(d) == FIELDS
    assert d["id"] == path.stem
    assert d["speaker"] == "adult"  # never a child (CLAUDE.md, child data)
    assert d["kind"] in KINDS
    assert d["text_id"] in load_builtin()
    assert d["audio"] == f"audio-local/{d['id']}.wav"
    assert all(set(m) == {"word", "mark", "heard"} and m["mark"] in MARKS for m in d["expected_marks"])


@pytest.mark.parametrize("path", SIDECARS, ids=lambda p: p.stem)
def test_expected_marks_agree_with_the_aligner_on_the_reference_transcript(path: Path):
    d = _load(path)
    text = load_builtin()[d["text_id"]].text
    got = [{"word": w.word, "mark": str(w.mark), "heard": w.heard} for w in align(text, d["reference_transcript"])]
    assert got == d["expected_marks"]


@pytest.mark.parametrize("path", SIDECARS, ids=lambda p: p.stem)
def test_every_planned_clip_is_in_the_manifest(path: Path):
    assert f"`{_load(path)['audio']}`" in MANIFEST.read_text(encoding="utf-8")

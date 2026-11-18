"""Testing log (ADR 0001): SQLite schema v1, immutable engine marks, Delete all, per-attempt secure delete.

Everything runs under tmp_path with invented values; never the repo's data/.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from reading_tutor.storage.files import Layout, delete_all, delete_attempt
from reading_tutor.storage.log import SCHEMA_VERSION, Log, SchemaTooNew

pytestmark = pytest.mark.integration

ATTEMPT = {
    "text_id": "t1-test",
    "text_level": 1,
    "text_version_hash": "abc123",
    "speaker_kind": "adult_fixture",
    "speaker_code": "A1",
    "input_device_class": "builtin",
    "input_device_hash": "deadbeef",
    "mime_type": "audio/webm;codecs=opus",
    "track_settings": {"sampleRate": 48000, "channelCount": 1, "autoGainControl": True},
    "audio_duration_s": 3.5,
    "derived_wav_sha256": "0" * 64,
    "core_version": "0.1.0",
    "similarity_fn": "rapidfuzz.Levenshtein.normalized_similarity",
    "unsure_threshold": 0.8,
    "original_ext": "webm",
}

RUN = {
    "engine_id": "fake",
    "model": "fake-1",
    "compute_type": "none",
    "prompt_variant": "none",
    "vad_settings": {"min_silence_duration_ms": 1000},
    "decoding_settings": {"condition_on_previous_text": False},
    "audio_destination": "local",
    "run_status": "ok",
    "model_load_s": 0.1,
    "transcribe_wall_s": 0.2,
    "cold_start": True,
    "transcript": "мама мие",
}

WORDS = [
    {"word_index": 0, "expected_token": "мама", "engine_mark": "correct", "heard_text": "мама", "similarity": 1.0},
    {"word_index": 1, "expected_token": "мие", "engine_mark": "correct", "heard_text": "мие", "similarity": 1.0},
    {"word_index": 2, "expected_token": "рамо", "engine_mark": "skipped", "heard_text": None, "similarity": None},
]


@pytest.fixture
def layout(tmp_path: Path) -> Layout:
    lay = Layout(tmp_path / "data")
    lay.ensure()
    return lay


@pytest.fixture
def log(layout: Layout):
    lg = Log(layout.db)
    yield lg
    lg.close()


def test_fresh_log_has_schema_v1_and_every_adr_table(log: Log, layout: Layout):
    assert SCHEMA_VERSION == 1
    con = sqlite3.connect(layout.db)
    try:
        assert con.execute("PRAGMA user_version").fetchone()[0] == 1
        tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        con.close()
    assert {"attempts", "runs", "words", "parent_marks", "texts"} <= tables


def test_attempt_table_has_every_adr_0001_field(layout: Layout, log: Log):
    con = sqlite3.connect(layout.db)
    try:
        cols = {r[1] for r in con.execute("PRAGMA table_info(attempts)")}
        run_cols = {r[1] for r in con.execute("PRAGMA table_info(runs)")}
        word_cols = {r[1] for r in con.execute("PRAGMA table_info(words)")}
        parent_cols = {r[1] for r in con.execute("PRAGMA table_info(parent_marks)")}
    finally:
        con.close()
    assert {
        "attempt_id", "recorded_at", "schema_version", "text_id", "text_level", "text_version_hash",
        "speaker_kind", "speaker_code", "input_device_class", "input_device_hash", "mime_type", "track_settings",
        "room_condition", "mic_distance", "audio_duration_s", "derived_wav_sha256", "whole_attempt_reviewed",
        "reviewed_at", "displayed_engine_id", "core_version", "similarity_fn", "unsure_threshold",
    } <= cols  # fmt: skip
    assert "input_device_label" not in cols  # the raw label is never stored
    assert {
        "run_id", "attempt_id", "engine_id", "model", "compute_type", "prompt_variant", "vad_settings",
        "decoding_settings", "audio_destination", "run_status", "model_load_s", "transcribe_wall_s", "cold_start",
        "peak_ram_mb", "transcript",
    } <= run_cols  # fmt: skip
    assert {"run_id", "word_index", "expected_token", "engine_mark", "heard_text", "similarity"} <= word_cols
    assert {"attempt_id", "word_index", "parent_mark", "parent_mark_source"} <= parent_cols


def test_attempt_round_trip(log: Log):
    aid = log.add_attempt(ATTEMPT)
    row = log.get_attempt(aid)
    assert row is not None
    assert row["text_id"] == "t1-test"
    assert row["track_settings"] == ATTEMPT["track_settings"]
    assert row["schema_version"] == 1
    assert row["whole_attempt_reviewed"] is False
    assert row["recorded_at"]


def test_attempt_id_may_be_given(log: Log):
    assert log.add_attempt(ATTEMPT, attempt_id="c" * 32) == "c" * 32
    assert log.get_attempt("c" * 32) is not None


def test_unknown_attempt_field_is_refused(log: Log):
    with pytest.raises(ValueError, match="unknown"):
        log.add_attempt({**ATTEMPT, "child_name": "x"})


@pytest.mark.parametrize(
    ("field", "value"),
    [("speaker_kind", "parent"), ("input_device_class", "airpods")],
)
def test_enumerated_fields_are_checked_by_the_schema(log: Log, field: str, value: str):
    with pytest.raises(sqlite3.IntegrityError):
        log.add_attempt({**ATTEMPT, field: value})


def test_run_and_words_round_trip(log: Log):
    aid = log.add_attempt(ATTEMPT)
    rid = log.add_run(aid, RUN, WORDS)
    runs = log.get_runs(aid)
    assert [r["run_id"] for r in runs] == [rid]
    assert runs[0]["vad_settings"] == RUN["vad_settings"]
    assert runs[0]["cold_start"] is True
    words = log.get_words(rid)
    assert [w["engine_mark"] for w in words] == ["correct", "correct", "skipped"]
    assert words[2]["heard_text"] is None


def test_run_status_is_checked(log: Log):
    aid = log.add_attempt(ATTEMPT)
    with pytest.raises(sqlite3.IntegrityError):
        log.add_run(aid, {**RUN, "run_status": "maybe"}, [])


def test_engine_mark_is_immutable(log: Log, layout: Layout):
    aid = log.add_attempt(ATTEMPT)
    rid = log.add_run(aid, RUN, WORDS)
    con = sqlite3.connect(layout.db)
    try:
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            con.execute("UPDATE words SET engine_mark='misread' WHERE run_id=? AND word_index=0", (rid,))
    finally:
        con.close()
    assert log.get_words(rid)[0]["engine_mark"] == "correct"


def test_parent_marks_table_starts_empty(log: Log):
    log.add_attempt(ATTEMPT)
    assert log.count("parent_marks") == 0


def test_pasted_text_round_trip(log: Log):
    log.add_text({"text_id": "u-1", "level": None, "title": "Моят текст", "text": "Мама мие.", "text_version_hash": "h"})
    assert log.get_text("u-1")["text"] == "Мама мие."
    assert log.get_text("missing") is None
    assert [t["text_id"] for t in log.list_texts()] == ["u-1"]


def test_newer_schema_is_refused(layout: Layout):
    con = sqlite3.connect(layout.db)
    con.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 1}")
    con.close()
    with pytest.raises(SchemaTooNew):
        Log(layout.db)


def test_reopen_keeps_rows_and_does_not_remigrate(layout: Layout):
    lg = Log(layout.db)
    aid = lg.add_attempt(ATTEMPT)
    lg.close()
    lg2 = Log(layout.db)
    try:
        assert lg2.get_attempt(aid) is not None
    finally:
        lg2.close()


def _fill(layout: Layout, log: Log, side_files: bool = True) -> str:
    aid = log.add_attempt(ATTEMPT)
    log.add_run(aid, RUN, WORDS)
    d = layout.attempt_dir(aid)
    d.mkdir(parents=True)
    (d / "original.webm").write_bytes(b"fake-audio")
    (d / "derived.wav").write_bytes(b"fake-wav")
    (layout.exports / "export.csv").write_text("a,b\n")
    (layout.tmp / "upload.part").write_bytes(b"x")
    for side in ("-wal", "-shm", "-journal") if side_files else ():
        layout.db.with_name(layout.db.name + side).write_bytes(b"stale")
    return aid


def test_delete_all_leaves_only_a_fresh_empty_db(layout: Layout, log: Log):
    _fill(layout, log)
    fresh = delete_all(layout, log)
    try:
        assert sorted(p.name for p in layout.root.iterdir()) == ["log.sqlite"]
        assert fresh.count("attempts") == fresh.count("runs") == fresh.count("words") == 0
        assert fresh.count("texts") == 0
    finally:
        fresh.close()


def test_delete_all_twice_is_fine(layout: Layout, log: Log):
    _fill(layout, log)
    first = delete_all(layout, log)
    second = delete_all(layout, first)
    try:
        assert [p.name for p in layout.root.iterdir()] == ["log.sqlite"]
    finally:
        second.close()


def test_delete_all_refuses_a_stray_file(layout: Layout, log: Log, monkeypatch: pytest.MonkeyPatch):
    """Verification is real: anything left behind (here, a file the remover misses) raises."""
    _fill(layout, log)
    (layout.root / "stray.txt").write_text("x")
    import reading_tutor.storage.files as files

    monkeypatch.setattr(files, "_REMOVE", ("audio", "exports", "tmp"))
    with pytest.raises(RuntimeError, match="stray.txt"):
        delete_all(layout, log)


def test_delete_attempt_removes_rows_and_files_with_secure_delete(layout: Layout, log: Log):
    keep = _fill(layout, log, side_files=False)
    secret = "тайнаизречение" * 20  # invented; must not survive in SQLite's free pages
    gone = log.add_attempt(ATTEMPT)
    log.add_run(gone, {**RUN, "transcript": secret}, WORDS)
    layout.attempt_dir(gone).mkdir(parents=True)
    (layout.attempt_dir(gone) / "derived.wav").write_bytes(b"x")
    assert secret.encode() in layout.db.read_bytes()

    delete_attempt(layout, log, gone)

    assert log.get_attempt(gone) is None
    assert log.get_runs(gone) == []
    assert not layout.attempt_dir(gone).exists()
    assert log.get_attempt(keep) is not None
    log.close()
    assert secret.encode() not in layout.db.read_bytes()


@pytest.mark.parametrize("bad", ["../x", "a/b", "", "ABC", "x" * 33])
def test_attempt_dir_refuses_odd_ids(layout: Layout, bad: str):
    with pytest.raises(ValueError):
        layout.attempt_dir(bad)

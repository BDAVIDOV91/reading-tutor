"""The testing log (ADR 0001): one SQLite file, schema v1, forward-only migrations.

Engine marks are written once: a trigger refuses any UPDATE of a word row. Parent marks live in their own table
(empty until step 3). JSON-valued fields (track settings, VAD and decoding settings) are stored as JSON text.
Logs from this module carry ids only, never text.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import uuid
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1

_V1 = """
CREATE TABLE texts (
    text_id TEXT PRIMARY KEY,
    level INTEGER,
    title TEXT NOT NULL,
    text TEXT NOT NULL,
    text_version_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE attempts (
    attempt_id TEXT PRIMARY KEY,
    recorded_at TEXT NOT NULL,
    schema_version INTEGER NOT NULL,
    text_id TEXT NOT NULL,
    text_level INTEGER,
    text_version_hash TEXT NOT NULL,
    speaker_kind TEXT NOT NULL CHECK (speaker_kind IN ('child', 'adult_fixture')),
    speaker_code TEXT NOT NULL,
    input_device_class TEXT NOT NULL
        CHECK (input_device_class IN ('builtin', 'usb', 'bluetooth', 'headset', 'unknown')),
    input_device_hash TEXT,
    mime_type TEXT,
    track_settings TEXT,
    room_condition TEXT CHECK (room_condition IS NULL OR room_condition IN ('quiet', 'noisy')),
    mic_distance TEXT CHECK (mic_distance IS NULL OR mic_distance IN ('near', 'far')),
    audio_duration_s REAL,
    derived_wav_sha256 TEXT,
    original_ext TEXT,
    whole_attempt_reviewed INTEGER NOT NULL DEFAULT 0,
    reviewed_at TEXT,
    displayed_engine_id TEXT,
    core_version TEXT NOT NULL,
    similarity_fn TEXT NOT NULL,
    unsure_threshold REAL NOT NULL
);
CREATE TABLE runs (
    run_id TEXT PRIMARY KEY,
    attempt_id TEXT NOT NULL REFERENCES attempts (attempt_id) ON DELETE CASCADE,
    engine_id TEXT NOT NULL,
    model TEXT NOT NULL,
    compute_type TEXT,
    prompt_variant TEXT NOT NULL CHECK (prompt_variant IN ('none', 'target_text')),
    vad_settings TEXT,
    decoding_settings TEXT,
    audio_destination TEXT NOT NULL,
    run_status TEXT NOT NULL CHECK (run_status IN ('ok', 'failed', 'timeout')),
    error_kind TEXT,
    model_load_s REAL,
    transcribe_wall_s REAL,
    cold_start INTEGER,
    peak_ram_mb REAL,
    transcript TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX runs_attempt ON runs (attempt_id);
CREATE TABLE words (
    run_id TEXT NOT NULL REFERENCES runs (run_id) ON DELETE CASCADE,
    word_index INTEGER NOT NULL,
    expected_token TEXT NOT NULL,
    engine_mark TEXT NOT NULL
        CHECK (engine_mark IN ('correct', 'misread', 'skipped', 'unsure', 'not_attempted')),
    heard_text TEXT,
    similarity REAL,
    PRIMARY KEY (run_id, word_index)
);
CREATE TRIGGER words_engine_mark_immutable BEFORE UPDATE ON words
BEGIN
    SELECT RAISE(ABORT, 'engine_mark is immutable: words are written once (ADR 0001)');
END;
CREATE TABLE parent_marks (
    attempt_id TEXT NOT NULL REFERENCES attempts (attempt_id) ON DELETE CASCADE,
    word_index INTEGER NOT NULL,
    parent_mark TEXT NOT NULL CHECK (parent_mark IN
        ('correct', 'misread', 'skipped', 'not_attempted', 'self_corrected_correct')),
    parent_mark_source TEXT NOT NULL CHECK (parent_mark_source IN ('explicit_tap', 'default_on_review')),
    marked_at TEXT NOT NULL,
    PRIMARY KEY (attempt_id, word_index)
);
CREATE TABLE install (
    key TEXT PRIMARY KEY,
    value BLOB NOT NULL
);
"""

# Forward-only: entry i migrates user_version i -> i + 1. Never edit an entry once committed; append a new one.
MIGRATIONS: tuple[str, ...] = (_V1,)

_JSON_FIELDS = {"track_settings", "vad_settings", "decoding_settings"}
_BOOL_FIELDS = {"whole_attempt_reviewed", "cold_start"}

ATTEMPT_FIELDS = frozenset(
    {
        "text_id", "text_level", "text_version_hash", "speaker_kind", "speaker_code", "input_device_class",
        "input_device_hash", "mime_type", "track_settings", "room_condition", "mic_distance", "audio_duration_s",
        "derived_wav_sha256", "original_ext", "displayed_engine_id", "core_version", "similarity_fn",
        "unsure_threshold",
    }
)  # fmt: skip
RUN_FIELDS = frozenset(
    {
        "engine_id", "model", "compute_type", "prompt_variant", "vad_settings", "decoding_settings",
        "audio_destination", "run_status", "error_kind", "model_load_s", "transcribe_wall_s", "cold_start",
        "peak_ram_mb", "transcript",
    }
)  # fmt: skip
WORD_FIELDS = ("word_index", "expected_token", "engine_mark", "heard_text", "similarity")
TEXT_FIELDS = frozenset({"text_id", "level", "title", "text", "text_version_hash"})
TABLES = ("texts", "attempts", "runs", "words", "parent_marks")


class SchemaTooNew(RuntimeError):
    """The file was written by a newer version of the app; refuse rather than guess."""


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _new_id() -> str:
    return uuid.uuid4().hex


def _encode(row: Mapping[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in row.items():
        if k in _JSON_FIELDS and v is not None:
            v = json.dumps(v, ensure_ascii=False, sort_keys=True)
        elif k in _BOOL_FIELDS and v is not None:
            v = int(bool(v))
        out[k] = v
    return out


def _decode(row: sqlite3.Row) -> dict[str, Any]:
    out = dict(row)
    for k in _JSON_FIELDS & out.keys():
        if out[k] is not None:
            out[k] = json.loads(out[k])
    for k in _BOOL_FIELDS & out.keys():
        if out[k] is not None:
            out[k] = bool(out[k])
    return out


def _check(row: Mapping[str, Any], allowed: frozenset[str], what: str) -> None:
    unknown = set(row) - allowed
    if unknown:
        raise ValueError(f"unknown {what} fields: {sorted(unknown)}")


class Log:
    """One open connection, shared across threads behind a lock (the server's worker thread writes runs)."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._con: sqlite3.Connection | None = sqlite3.connect(self.path, check_same_thread=False)
        self._con.row_factory = sqlite3.Row
        self._con.execute("PRAGMA foreign_keys = ON")
        self._migrate()

    # --- lifecycle -------------------------------------------------------------------------------------------

    def _migrate(self) -> None:
        con = self._db()
        version = con.execute("PRAGMA user_version").fetchone()[0]
        if version > SCHEMA_VERSION:
            self.close()
            raise SchemaTooNew(f"log schema {version} is newer than this app ({SCHEMA_VERSION})")
        for target in range(version + 1, SCHEMA_VERSION + 1):
            with con:
                con.executescript(f"BEGIN; {MIGRATIONS[target - 1]} PRAGMA user_version = {target}; COMMIT;")

    def close(self) -> None:
        with self._lock:
            if self._con is not None:
                self._con.close()
                self._con = None

    def _db(self) -> sqlite3.Connection:
        if self._con is None:
            raise RuntimeError("log is closed")
        return self._con

    # --- texts -----------------------------------------------------------------------------------------------

    def add_text(self, row: Mapping[str, Any]) -> str:
        _check(row, TEXT_FIELDS, "text")
        data = {**row, "created_at": _now()}
        self._insert("texts", data)
        return data["text_id"]

    def get_text(self, text_id: str) -> dict[str, Any] | None:
        return self._one("SELECT * FROM texts WHERE text_id = ?", (text_id,))

    def list_texts(self) -> list[dict[str, Any]]:
        return self._all("SELECT * FROM texts ORDER BY created_at, text_id", ())

    # --- attempts and runs -----------------------------------------------------------------------------------

    def add_attempt(self, row: Mapping[str, Any], *, attempt_id: str | None = None) -> str:
        """`attempt_id` lets the caller name the audio directory before the row exists (the server does)."""
        _check(row, ATTEMPT_FIELDS, "attempt")
        aid = attempt_id or _new_id()
        self._insert(
            "attempts",
            {**_encode(row), "attempt_id": aid, "recorded_at": _now(), "schema_version": SCHEMA_VERSION},
        )
        return aid

    def get_attempt(self, attempt_id: str) -> dict[str, Any] | None:
        return self._one("SELECT * FROM attempts WHERE attempt_id = ?", (attempt_id,))

    def add_run(self, attempt_id: str, run: Mapping[str, Any], words: Iterable[Mapping[str, Any]]) -> str:
        """The run and all its words in one transaction: a run is never half written."""
        _check(run, RUN_FIELDS, "run")
        rid = _new_id()
        data = {**_encode(run), "run_id": rid, "attempt_id": attempt_id, "created_at": _now()}
        cols = ", ".join(data)
        marks = ", ".join("?" for _ in data)
        with self._lock:
            con = self._db()
            with con:
                con.execute(f"INSERT INTO runs ({cols}) VALUES ({marks})", tuple(data.values()))
                con.executemany(
                    "INSERT INTO words (run_id, word_index, expected_token, engine_mark, heard_text, similarity)"
                    " VALUES (?, ?, ?, ?, ?, ?)",
                    [(rid, *(w[f] for f in WORD_FIELDS)) for w in words],
                )
        return rid

    def get_runs(self, attempt_id: str) -> list[dict[str, Any]]:
        return self._all("SELECT * FROM runs WHERE attempt_id = ? ORDER BY created_at, run_id", (attempt_id,))

    def get_words(self, run_id: str) -> list[dict[str, Any]]:
        return self._all("SELECT * FROM words WHERE run_id = ? ORDER BY word_index", (run_id,))

    def delete_attempt(self, attempt_id: str) -> None:
        """Rows go with secure_delete on, so the text is overwritten, not left in free pages (ADR 0001)."""
        with self._lock:
            con = self._db()
            con.execute("PRAGMA secure_delete = ON")
            try:
                with con:
                    con.execute("DELETE FROM attempts WHERE attempt_id = ?", (attempt_id,))
            finally:
                con.execute("PRAGMA secure_delete = OFF")

    def device_secret(self) -> bytes:
        """Per-install key for device hashes, created on first use; Delete all replaces it with the database."""
        with self._lock:
            con = self._db()
            row = con.execute("SELECT value FROM install WHERE key = 'device_secret'").fetchone()
            if row is not None:
                return bytes(row[0])
            secret = os.urandom(32)
            with con:
                con.execute("INSERT INTO install (key, value) VALUES ('device_secret', ?)", (secret,))
            return secret

    def count(self, table: str) -> int:
        if table not in TABLES:
            raise ValueError(f"unknown table {table!r}")
        with self._lock:
            return self._db().execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    # --- helpers ---------------------------------------------------------------------------------------------

    def _insert(self, table: str, data: Mapping[str, Any]) -> None:
        cols = ", ".join(data)
        marks = ", ".join("?" for _ in data)
        with self._lock:
            con = self._db()
            with con:
                con.execute(f"INSERT INTO {table} ({cols}) VALUES ({marks})", tuple(data.values()))

    def _one(self, sql: str, args: tuple) -> dict[str, Any] | None:
        with self._lock:
            row = self._db().execute(sql, args).fetchone()
        return _decode(row) if row is not None else None

    def _all(self, sql: str, args: tuple) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._db().execute(sql, args).fetchall()
        return [_decode(r) for r in rows]

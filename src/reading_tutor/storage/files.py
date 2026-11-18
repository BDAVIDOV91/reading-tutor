"""The data/ layout (ADR 0001) and the two deletes.

    data/log.sqlite                    the testing log (+ -wal / -shm / -journal side files while open)
    data/audio/<attempt_id>/           original.<ext> (untouched upload) and derived.wav (16 kHz mono)
    data/exports/                      CSV exports (later step)
    data/tmp/                          every temporary and conversion file

Path names carry the attempt id only (32 lowercase hex characters), never a name or an age.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from reading_tutor.storage.log import TABLES, Log

_ATTEMPT_ID = re.compile(r"^[0-9a-f]{32}$")
_DB_NAME = "log.sqlite"
_DB_SIDE = ("-wal", "-shm", "-journal")
_REMOVE = ("audio", "exports", "tmp")  # every directory Delete all removes; patched only by a test


@dataclass(frozen=True)
class Layout:
    root: Path

    @property
    def db(self) -> Path:
        return self.root / _DB_NAME

    @property
    def audio(self) -> Path:
        return self.root / "audio"

    @property
    def exports(self) -> Path:
        return self.root / "exports"

    @property
    def tmp(self) -> Path:
        return self.root / "tmp"

    def ensure(self) -> None:
        for d in (self.root, self.audio, self.exports, self.tmp):
            d.mkdir(parents=True, exist_ok=True)

    def attempt_dir(self, attempt_id: str) -> Path:
        if not _ATTEMPT_ID.fullmatch(attempt_id):
            raise ValueError("attempt id must be 32 lowercase hex characters")
        return self.audio / attempt_id


def _remove(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    elif path.exists() or path.is_symlink():
        path.unlink()


def delete_all(layout: Layout, log: Log) -> Log:
    """Close the log, remove the database with its side files and every data directory, then reopen a fresh
    empty log and verify that it is the only thing left. Returns the new open log."""
    log.close()
    for side in ("", *_DB_SIDE):
        _remove(layout.db.with_name(_DB_NAME + side))
    for name in _REMOVE:
        _remove(layout.root / name)

    fresh = Log(layout.db)
    left = sorted(p.name for p in layout.root.iterdir())
    rows = sum(fresh.count(t) for t in TABLES)
    if left != [_DB_NAME] or rows:
        fresh.close()
        raise RuntimeError(f"Delete all did not finish: left {left}, {rows} rows")
    return fresh


def delete_attempt(layout: Layout, log: Log, attempt_id: str) -> None:
    """One attempt: its rows (secure delete) and its audio directory."""
    target = layout.attempt_dir(attempt_id)
    log.delete_attempt(attempt_id)
    _remove(target)

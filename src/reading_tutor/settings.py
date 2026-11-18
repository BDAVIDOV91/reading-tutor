"""Runtime settings, read from the environment once at app start.

The host is a constant, not a setting: the server listens on loopback only (ADR 0002, child-data rules).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

HOST = "127.0.0.1"
PORT = 8000
MAX_RECORDING_S = 300  # the page stops recording automatically after 5 minutes (step 2 plan S8)

DATA_DIR_ENV = "READING_TUTOR_DATA_DIR"
CHILD_FLAG = "READING_TUTOR_CHILD_RECORDING"  # ADR 0003 turns this on; until then only adults are recorded
ENGINE_ENV = "READING_TUTOR_ENGINE"
FAKE_FLAG = "READING_TUTOR_FAKE_ENGINE"

DEFAULT_DATA_DIR = Path(__file__).resolve().parents[2] / "data"


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    child_recording_allowed: bool
    engine: str


def load_settings() -> Settings:
    default_engine = "fake" if os.environ.get(FAKE_FLAG) else "whisper-turbo"
    data_dir = Path(os.environ.get(DATA_DIR_ENV) or DEFAULT_DATA_DIR)
    repo = DEFAULT_DATA_DIR.parent
    resolved = data_dir.resolve()
    if resolved.is_relative_to(repo) and not resolved.is_relative_to(DEFAULT_DATA_DIR.resolve()):
        # Inside the repo only data/ is gitignored and kept off M2 (privacy review 2026-11-18, finding 9).
        raise ValueError(f"{DATA_DIR_ENV} inside the repo must be the data/ directory")
    return Settings(
        data_dir=data_dir,
        child_recording_allowed=os.environ.get(CHILD_FLAG) == "1",
        engine=os.environ.get(ENGINE_ENV) or default_engine,
    )

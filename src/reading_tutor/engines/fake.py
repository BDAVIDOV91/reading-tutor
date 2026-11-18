"""Test-only engine: returns a fixed transcript (for e2e, a fixture sidecar's reference transcript).

Registered only when READING_TUTOR_FAKE_ENGINE names a sidecar file (engines/__init__.py).
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


class FakeEngine:
    engine_id = "fake"
    model = "fake-reference-transcript"
    compute_type = "none"
    audio_destination = "local"
    prompt_variant = "none"

    def __init__(self, transcript: str, *, fail: bool = False, delay_s: float = 0.0):
        self._transcript = transcript
        self._fail = fail
        self._delay_s = delay_s
        self._loaded = False
        self.vad_settings: dict[str, Any] = {}
        self.decoding_settings: dict[str, Any] = {}

    @classmethod
    def from_sidecar(cls, path: Path) -> FakeEngine:
        return cls(json.loads(path.read_text(encoding="utf-8"))["reference_transcript"])

    @property
    def loaded(self) -> bool:
        return self._loaded

    def load(self) -> None:
        self._loaded = True

    def transcribe(self, wav: Path) -> str:
        if self._delay_s:
            time.sleep(self._delay_s)
        if self._fail:
            raise RuntimeError("fake engine failure")
        return self._transcript

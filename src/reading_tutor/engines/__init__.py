"""Speech-to-text engines behind one interface (add-stt-engine skill; ADR 0001 engine-run fields).

An engine declares where audio goes (`audio_destination`: `local` or `cloud:<provider>:<region>`), its model and
its settings, loads lazily once, and turns a 16 kHz mono WAV into text. `run_engine` wraps every call: a failure
or a timeout comes back as a typed `EngineResult`, never an exception, and the recording is never touched.
"""

from __future__ import annotations

import os
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Protocol

from reading_tutor.settings import FAKE_FLAG

RunStatus = Literal["ok", "failed", "timeout"]
DEFAULT_TIMEOUT_S = 600.0


class Engine(Protocol):
    engine_id: str
    model: str
    compute_type: str
    audio_destination: str
    prompt_variant: str
    vad_settings: dict[str, Any]
    decoding_settings: dict[str, Any]

    @property
    def loaded(self) -> bool: ...

    def load(self) -> None: ...

    def transcribe(self, wav: Path) -> str: ...


@dataclass(frozen=True)
class EngineResult:
    run_status: RunStatus
    transcript: str | None
    model_load_s: float | None
    transcribe_wall_s: float | None
    cold_start: bool
    error_kind: str | None  # exception class name only, never its message (it may hold a path or text)


def run_engine(engine: Engine, wav: Path, *, timeout_s: float = DEFAULT_TIMEOUT_S) -> EngineResult:
    cold = not engine.loaded
    box: dict[str, Any] = {}

    def work() -> None:
        try:
            t0 = time.perf_counter()
            if not engine.loaded:
                engine.load()
            box["load"] = round(time.perf_counter() - t0, 3) if cold else 0.0
            t1 = time.perf_counter()
            box["text"] = engine.transcribe(wav)
            box["wall"] = round(time.perf_counter() - t1, 3)
        except Exception as e:  # noqa: BLE001 - every engine failure becomes a typed result
            box["error"] = type(e).__name__

    worker = threading.Thread(target=work, name=f"engine-{engine.engine_id}", daemon=True)
    worker.start()
    worker.join(timeout_s)
    if worker.is_alive():
        return EngineResult("timeout", None, None, None, cold, "Timeout")
    if "error" in box:
        return EngineResult("failed", None, box.get("load"), None, cold, box["error"])
    return EngineResult("ok", box["text"], box["load"], box["wall"], cold, None)


def _factories() -> dict[str, Callable[[], Engine]]:
    from reading_tutor.engines.whisper import WhisperTurbo

    out: dict[str, Callable[[], Engine]] = {"whisper-turbo": WhisperTurbo}
    sidecar = os.environ.get(FAKE_FLAG)
    if sidecar:  # test-only engine; never present unless the flag names a fixture sidecar
        from reading_tutor.engines.fake import FakeEngine

        out["fake"] = lambda: FakeEngine.from_sidecar(Path(sidecar))
    return out


def available_engines() -> list[str]:
    return sorted(_factories())


def make_engine(name: str) -> Engine:
    factories = _factories()
    if name not in factories:
        raise KeyError(f"unknown engine {name!r}")
    return factories[name]()

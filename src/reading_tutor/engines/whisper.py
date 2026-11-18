"""Whisper large-v3 turbo through faster-whisper, CPU int8, local (step 2 plan S4; speed spike 2026-11-18).

No prompt and no target text: biasing toward the text could hide the misreadings the app exists to find
(add-stt-engine step 5). The WAV is decoded with soundfile, because faster-whisper 1.2.1's PyAV path breaks on
current `av` ("metadata_errors", found in the speed spike).
"""

from __future__ import annotations

import os
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

MODEL_ID = "deepdml/faster-whisper-large-v3-turbo-ct2"
# Pinned; loaded from the local HF cache only, so a model load never contacts Hugging Face (privacy review
# 2026-11-18, finding 7). One-time download: `uv run hf download <MODEL_ID> --revision <MODEL_REVISION>`.
MODEL_REVISION = "4df90f75321148c3a29a9e2351b7ddf8f5b115a8"
SAMPLE_RATE = 16000


def _load_model() -> Any:
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
    from faster_whisper import WhisperModel

    return WhisperModel(
        MODEL_ID,
        device="cpu",
        compute_type="int8",
        cpu_threads=os.cpu_count() or 4,
        revision=MODEL_REVISION,
        local_files_only=True,
    )


class WhisperTurbo:
    engine_id = "whisper-turbo"
    model = f"{MODEL_ID}@{MODEL_REVISION[:12]}"
    compute_type = "int8"
    audio_destination = "local"
    prompt_variant = "none"

    def __init__(self, model_factory: Callable[[], Any] = _load_model):
        self._factory = model_factory
        self._model: Any = None
        self._lock = threading.Lock()  # one transcription at a time, even if a timed-out run is still going
        self.vad_settings: dict[str, Any] = {"vad_filter": True, "min_silence_duration_ms": 1000}
        self.decoding_settings: dict[str, Any] = {
            "language": "bg",
            "condition_on_previous_text": False,
            "beam_size": 5,
            "temperature": "default",
            "no_speech_threshold": "default",
        }

    @property
    def loaded(self) -> bool:
        return self._model is not None

    def load(self) -> None:
        with self._lock:
            if self._model is None:
                self._model = self._factory()

    def transcribe(self, wav: Path) -> str:
        import soundfile as sf

        data, sr = sf.read(str(wav), dtype="float32")
        if sr != SAMPLE_RATE:
            raise ValueError("expected 16 kHz audio")
        with self._lock:
            segments, _info = self._model.transcribe(
                data,
                language="bg",
                condition_on_previous_text=False,
                beam_size=5,
                vad_filter=True,
                vad_parameters={"min_silence_duration_ms": 1000},
            )
            return " ".join(s.text.strip() for s in segments).strip()  # the generator does the work

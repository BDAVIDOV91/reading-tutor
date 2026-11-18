"""WhisperTurbo with a mocked model: decoding through soundfile, settings passed, model loaded once and kept warm."""

from __future__ import annotations

import math
import struct
import wave
from pathlib import Path
from types import SimpleNamespace

import pytest

from reading_tutor.engines import run_engine
from reading_tutor.engines.whisper import WhisperTurbo

pytestmark = pytest.mark.integration


def _wav(path: Path, rate: int = 16000) -> Path:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"".join(struct.pack("<h", int(3000 * math.sin(i / 10))) for i in range(rate // 2)))
    return path


class _Model:
    def __init__(self):
        self.calls: list[dict] = []

    def transcribe(self, audio, **kwargs):
        self.calls.append({"n": len(audio), "dtype": str(audio.dtype), **kwargs})
        segs = (SimpleNamespace(text=t) for t in [" Ето мама", " и баба. "])
        return segs, SimpleNamespace(language="bg")


def test_mocked_whisper_transcribes_with_the_settled_settings(tmp_path: Path):
    model = _Model()
    loads: list[int] = []

    def factory():
        loads.append(1)
        return model

    eng = WhisperTurbo(model_factory=factory)
    wav = _wav(tmp_path / "a.wav")
    first = run_engine(eng, wav, timeout_s=10)
    second = run_engine(eng, wav, timeout_s=10)

    assert first.run_status == "ok"
    assert first.transcript == "Ето мама и баба."
    assert first.cold_start is True and second.cold_start is False
    assert second.model_load_s == 0.0
    assert loads == [1]  # loaded once, kept warm
    call = model.calls[0]
    assert call["n"] == 8000 and call["dtype"] == "float32"
    assert call["language"] == "bg"
    assert call["condition_on_previous_text"] is False
    assert call["vad_filter"] is True
    assert call["vad_parameters"] == {"min_silence_duration_ms": 1000}
    assert "initial_prompt" not in call  # never feed the target text (add-stt-engine step 5)


def test_wrong_sample_rate_fails_typed(tmp_path: Path):
    eng = WhisperTurbo(model_factory=_Model)
    res = run_engine(eng, _wav(tmp_path / "b.wav", rate=8000), timeout_s=10)
    assert res.run_status == "failed"
    assert res.error_kind == "ValueError"


def test_model_loads_from_local_files_at_a_pinned_revision(monkeypatch: pytest.MonkeyPatch):
    """Privacy review 2026-11-18, finding 7: no Hugging Face call at load time, weights pinned."""
    import faster_whisper

    from reading_tutor.engines import whisper

    seen: dict = {}
    monkeypatch.setattr(faster_whisper, "WhisperModel", lambda *a, **kw: seen.update(kw) or object())
    whisper._load_model()
    assert seen["local_files_only"] is True
    assert seen["revision"] == whisper.MODEL_REVISION == "4df90f75321148c3a29a9e2351b7ddf8f5b115a8"

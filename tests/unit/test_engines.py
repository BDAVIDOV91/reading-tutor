"""Engine interface (add-stt-engine skill): typed results, failure and timeout never lose the recording,
the audio destination is declared, and the fake engine exists only when its env flag is set."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from reading_tutor.engines import EngineResult, available_engines, make_engine, run_engine
from reading_tutor.engines.fake import FakeEngine

pytestmark = pytest.mark.unit


def test_fake_engine_declares_local_and_returns_its_transcript(tmp_path: Path):
    wav = tmp_path / "x.wav"
    wav.write_bytes(b"RIFF")
    eng = FakeEngine(transcript="мама мие")
    assert eng.audio_destination == "local"
    assert eng.prompt_variant == "none"
    res = run_engine(eng, wav, timeout_s=5)
    assert res == EngineResult(
        run_status="ok", transcript="мама мие", model_load_s=0.0, transcribe_wall_s=res.transcribe_wall_s,
        cold_start=True, error_kind=None,
    )  # fmt: skip
    assert res.transcribe_wall_s is not None and res.transcribe_wall_s >= 0
    assert run_engine(eng, wav, timeout_s=5).cold_start is False


def test_failure_comes_back_typed_and_keeps_the_recording(tmp_path: Path):
    wav = tmp_path / "x.wav"
    wav.write_bytes(b"RIFF")
    res = run_engine(FakeEngine(transcript="", fail=True), wav, timeout_s=5)
    assert res.run_status == "failed"
    assert res.transcript is None
    assert res.error_kind == "RuntimeError"
    assert wav.exists()


def test_timeout_comes_back_typed_and_keeps_the_recording(tmp_path: Path):
    wav = tmp_path / "x.wav"
    wav.write_bytes(b"RIFF")
    t0 = time.perf_counter()
    res = run_engine(FakeEngine(transcript="x", delay_s=2.0), wav, timeout_s=0.2)
    assert time.perf_counter() - t0 < 1.5
    assert res.run_status == "timeout"
    assert res.transcript is None
    assert wav.exists()


def test_registry_has_no_fake_without_the_flag(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("READING_TUTOR_FAKE_ENGINE", raising=False)
    assert "fake" not in available_engines()
    assert "whisper-turbo" in available_engines()
    with pytest.raises(KeyError):
        make_engine("fake")


def test_registry_fake_reads_the_sidecar_named_by_the_flag(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    sidecar = tmp_path / "f.json"
    sidecar.write_text(json.dumps({"reference_transcript": "ето мама"}), encoding="utf-8")
    monkeypatch.setenv("READING_TUTOR_FAKE_ENGINE", str(sidecar))
    assert "fake" in available_engines()
    eng = make_engine("fake")
    wav = tmp_path / "x.wav"
    wav.write_bytes(b"RIFF")
    assert run_engine(eng, wav, timeout_s=5).transcript == "ето мама"


def test_make_engine_unknown_name():
    with pytest.raises(KeyError):
        make_engine("nope")


def test_whisper_declares_its_settings_without_loading_the_model():
    eng = make_engine("whisper-turbo")
    assert eng.engine_id == "whisper-turbo"
    assert eng.model == "deepdml/faster-whisper-large-v3-turbo-ct2@4df90f753211"  # ADR 0001: name and revision
    assert eng.audio_destination == "local"
    assert eng.prompt_variant == "none"
    assert eng.compute_type == "int8"
    assert eng.vad_settings == {"vad_filter": True, "min_silence_duration_ms": 1000}
    assert eng.decoding_settings["condition_on_previous_text"] is False
    assert eng.decoding_settings["language"] == "bg"
    assert "initial_prompt" not in eng.decoding_settings
    assert eng.loaded is False

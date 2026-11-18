"""Audio derivation through ffmpeg: original upload untouched, derived 16 kHz mono WAV, duration and sha256.

Uses a generated sine WAV under tmp_path (synthetic, no voice).
"""

from __future__ import annotations

import hashlib
import math
import struct
import wave
from pathlib import Path

import pytest

from reading_tutor.audio import AudioError, derive_wav, wav_duration_s
from reading_tutor.storage.files import Layout

pytestmark = pytest.mark.integration


def _sine(path: Path, seconds: float = 1.5, rate: int = 44100, channels: int = 2) -> Path:
    frames = int(seconds * rate)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(rate)
        samples = (int(8000 * math.sin(2 * math.pi * 440 * i / rate)) for i in range(frames))
        w.writeframes(b"".join(struct.pack("<h", s) * channels for s in samples))
    return path


@pytest.fixture
def layout(tmp_path: Path) -> Layout:
    lay = Layout(tmp_path / "data")
    lay.ensure()
    return lay


def test_derive_wav_makes_16k_mono_and_keeps_the_original(layout: Layout, tmp_path: Path):
    original = _sine(tmp_path / "original.wav")
    before = original.read_bytes()
    dest = layout.audio / ("a" * 32) / "derived.wav"
    info = derive_wav(original, dest, tmp_dir=layout.tmp)

    assert original.read_bytes() == before
    with wave.open(str(dest)) as w:
        assert (w.getframerate(), w.getnchannels(), w.getsampwidth()) == (16000, 1, 2)
    assert info.duration_s == pytest.approx(1.5, abs=0.05)
    assert info.sha256 == hashlib.sha256(dest.read_bytes()).hexdigest()
    assert list(layout.tmp.iterdir()) == []  # the temp file was moved into place, nothing left behind


def test_derive_wav_failure_is_typed_and_leaves_nothing(layout: Layout, tmp_path: Path):
    bad = tmp_path / "broken.webm"
    bad.write_bytes(b"not audio at all")
    dest = layout.audio / ("b" * 32) / "derived.wav"
    with pytest.raises(AudioError) as err:
        derive_wav(bad, dest, tmp_dir=layout.tmp)
    assert str(Path.home()) not in str(err.value)  # no path under home in an error (child-data rule)
    assert not dest.exists()
    assert list(layout.tmp.iterdir()) == []


def test_wav_duration(tmp_path: Path):
    assert wav_duration_s(_sine(tmp_path / "x.wav", seconds=0.5, rate=16000, channels=1)) == pytest.approx(0.5)

"""Audio handling on the server: derive the 16 kHz mono WAV every engine reads, and classify the input device.

The original upload is never changed. Conversion runs through an ffmpeg subprocess into data/tmp/ and the result
is moved into place, so a half-written derived.wav never exists. Errors never carry a path or ffmpeg's stderr
(which names the file).
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import subprocess
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path

SAMPLE_RATE = 16000
FFMPEG_TIMEOUT_S = 120


class AudioError(RuntimeError):
    """The upload could not be turned into a WAV. The message is generic on purpose."""


@dataclass(frozen=True)
class DerivedAudio:
    path: Path
    duration_s: float
    sha256: str


def wav_duration_s(path: Path) -> float:
    with wave.open(str(path)) as w:
        return w.getnframes() / w.getframerate()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def derive_wav(original: Path, dest: Path, *, tmp_dir: Path) -> DerivedAudio:
    tmp_dir.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(suffix=".wav", dir=tmp_dir)
    os.close(fd)
    tmp = Path(tmp_name)
    try:
        cmd = [
            "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
            "-i", str(original), "-vn", "-ac", "1", "-ar", str(SAMPLE_RATE), "-c:a", "pcm_s16le", str(tmp),
        ]  # fmt: skip
        try:
            done = subprocess.run(cmd, capture_output=True, timeout=FFMPEG_TIMEOUT_S, check=False)
        except subprocess.TimeoutExpired as e:
            raise AudioError("audio conversion timed out") from e
        if done.returncode != 0 or tmp.stat().st_size == 0:
            raise AudioError(f"audio conversion failed (ffmpeg exit {done.returncode})")
        dest.parent.mkdir(parents=True, exist_ok=True)
        os.replace(tmp, dest)
    finally:
        tmp.unlink(missing_ok=True)
    return DerivedAudio(path=dest, duration_s=wav_duration_s(dest), sha256=_sha256(dest))


# --- input device ---------------------------------------------------------------------------------------------

_CLASSES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("bluetooth", re.compile(r"bluetooth|airpods|buds|hands-?free|bluez|\bbt\b", re.I)),
    ("usb", re.compile(r"\busb\b|\([0-9a-f]{4}:[0-9a-f]{4}\)", re.I)),
    ("headset", re.compile(r"headset|headphone", re.I)),
    ("builtin", re.compile(r"built-?in|internal|macbook|microphone array|^default$|default audio input|вграден", re.I)),
)


def device_class(label: str) -> str:
    """One of builtin, usb, bluetooth, headset, unknown. Never returns any part of the label."""
    for name, pattern in _CLASSES:
        if pattern.search(label or ""):
            return name
    return "unknown"


def device_hash(label: str, secret: bytes = b"") -> str | None:
    """Short keyed hash of the label, to tell devices apart without storing a name (ADR 0001).

    Keyed with a per-install secret kept in the log (Log.device_secret), so "<Name>'s AirPods" cannot be recovered
    by hashing guessed names; Delete all replaces the secret (privacy review 2026-11-18, finding 5).
    """
    if not label:
        return None
    return hmac.new(secret, label.encode("utf-8"), hashlib.sha256).hexdigest()[:12]

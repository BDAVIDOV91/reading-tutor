"""Real Whisper turbo on the 8 adult fixtures (owner's voice, tests/fixtures/audio-local/, local only).

Records each run's time and marks against the sidecar in tests/fixtures/audio-local/turbo-report.json (local,
gitignored). It asserts that every run completes; it does NOT assert accuracy: these are adult recordings, so
the numbers are "test-verified on an adult" only and never a statement about children (engine-eval skill).
A missing WAV fails loudly (step 2 plan S2), never skips.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from reading_tutor.audio import wav_duration_s
from reading_tutor.core import align
from reading_tutor.engines import run_engine
from reading_tutor.engines.whisper import WhisperTurbo
from reading_tutor.texts import load_builtin

pytestmark = pytest.mark.integration

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
SIDECARS = sorted((FIXTURES / "sidecars").glob("*.json"))
REPORT = FIXTURES / "audio-local" / "turbo-report.json"
_rows: list[dict] = []


@pytest.fixture(scope="module")
def engine() -> Iterator[WhisperTurbo]:
    yield WhisperTurbo()
    if _rows:
        REPORT.write_text(json.dumps(_rows, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


@pytest.mark.parametrize("path", SIDECARS, ids=lambda p: p.stem)
def test_turbo_on_adult_fixture(engine: WhisperTurbo, path: Path):
    side = json.loads(path.read_text(encoding="utf-8"))
    wav = FIXTURES / side["audio"]
    assert wav.is_file(), f"missing adult fixture {side['audio']}: record it (tests/fixtures/FIXTURES.md)"
    duration = wav_duration_s(wav)
    assert duration < 30.5, "fixture clips stay under 30 s"

    res = run_engine(engine, wav, timeout_s=300)
    assert res.run_status == "ok", res.error_kind

    marks = align(load_builtin()[side["text_id"]].text, res.transcript or "")
    expected = [m["mark"] for m in side["expected_marks"]]
    got = [str(m.mark) for m in marks]
    _rows.append(
        {
            "id": side["id"],
            "audio_s": round(duration, 2),
            "load_s": res.model_load_s,
            "transcribe_s": res.transcribe_wall_s,
            "rtf": round((res.transcribe_wall_s or 0) / duration, 3),
            "words": len(expected),
            "agree": sum(a == b for a, b in zip(expected, got, strict=True)),
            "diffs": [
                {"i": i, "word": m.word, "expected": e, "got": str(m.mark), "heard": m.heard}
                for i, (e, m) in enumerate(zip(expected, marks, strict=True))
                if e != str(m.mark)
            ],
            "transcript": res.transcript,  # adult fixture: may be shown (step 2 plan, engines)
        }
    )

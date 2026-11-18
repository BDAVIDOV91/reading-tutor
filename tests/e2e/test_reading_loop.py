"""E2E: the whole loop in headless Chromium. Start -> read (fixture WAV as the fake microphone) -> Done ->
results with the right colours, replay, and no request leaving localhost.

The fake engine returns the fixture sidecar's reference transcript, so the marks must equal the sidecar's
expected marks. The `slow` test runs the same loop with real Whisper turbo (run with `-m slow`).
"test-verified" only: a headless browser with a fake microphone is never "laptop-verified" (ADR 0002).
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
import uuid
import wave
from collections.abc import Generator, Iterator
from pathlib import Path

import pytest

pytestmark = pytest.mark.e2e

REPO = Path(__file__).resolve().parents[2]
FIXTURES = REPO / "tests" / "fixtures"
BASE_CONFIG = REPO / ".playwright" / "cli.config.json"
COLOURS = {  # style.css
    "correct": "rgb(31, 122, 58)",
    "misread": "rgb(180, 83, 9)",
    "unsure": "rgb(180, 83, 9)",
    "skipped": "rgb(185, 28, 28)",
    "not_attempted": "rgb(138, 137, 132)",
}


def fixture_wav(sidecar: Path) -> Path:
    """The fake-microphone file: allow-listed to tests/fixtures/ (never recordings/ or data/), and present."""
    side = json.loads(sidecar.read_text(encoding="utf-8"))
    wav = (FIXTURES / side["audio"]).resolve()
    if not wav.is_relative_to(FIXTURES.resolve()):
        raise ValueError("fake-microphone audio must come from tests/fixtures/")
    assert wav.is_file(), f"missing adult fixture {side['audio']}: record it (tests/fixtures/FIXTURES.md)"
    return wav


def test_fake_mic_path_is_allow_listed(tmp_path: Path):
    bad = tmp_path / "x.json"
    bad.write_text(json.dumps({"audio": "../../data/audio/x/original.wav"}), encoding="utf-8")
    with pytest.raises(ValueError):
        fixture_wav(bad)


@pytest.fixture(scope="module")
def cli() -> str:
    path = shutil.which("playwright-cli")
    assert path, "playwright-cli not on PATH (docs/SKILLS.md)"
    return path


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _serve(tmp_path: Path, env_extra: dict[str, str]) -> Generator[str, None, None]:
    port = _free_port()
    env = {k: v for k, v in os.environ.items() if not k.startswith("READING_TUTOR_")}
    env.update({"READING_TUTOR_DATA_DIR": str(tmp_path / "data"), **env_extra})
    proc = subprocess.Popen(
        [sys.executable, "-m", "reading_tutor", "--port", str(port)],
        cwd=REPO, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )  # fmt: skip
    url = f"http://127.0.0.1:{port}"
    try:
        for _ in range(100):
            try:
                urllib.request.urlopen(f"{url}/api/config", timeout=1).close()
                break
            except OSError:
                time.sleep(0.1)
        else:
            raise AssertionError("server did not start")
        yield url
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def _run(cli: str, session: str, *args: str, timeout: int = 90) -> str:
    out = subprocess.run(
        [cli, f"-s={session}", *args], cwd=REPO, capture_output=True, text=True, timeout=timeout, check=False
    )
    assert out.returncode == 0, out.stdout + out.stderr
    return out.stdout


def _eval(cli: str, session: str, js: str, timeout: int = 90):
    return json.loads(_run(cli, session, "--raw", "eval", js, timeout=timeout) or "null")


def _read_loop(cli: str, url: str, wav: Path, text_id: str, tmp_path: Path, wait_s: float) -> dict:
    cfg = json.loads(BASE_CONFIG.read_text(encoding="utf-8"))
    cfg["browser"]["launchOptions"]["args"].append(f"--use-file-for-fake-audio-capture={wav}%noloop")
    config = tmp_path / "cli.config.json"
    config.write_text(json.dumps(cfg), encoding="utf-8")
    with wave.open(str(wav)) as w:
        clip_s = w.getnframes() / w.getframerate()

    session = f"e2e-{uuid.uuid4().hex[:8]}"
    try:
        _run(cli, session, "open", f"--config={config}", url)
        _eval(cli, session, "() => new Promise(r => { const t = setInterval(() => { "
              "if (document.getElementById('text-select').options.length) { clearInterval(t); r(true); } }, 50); })")  # fmt: skip
        _eval(cli, session, f"() => {{ const s = document.getElementById('text-select'); s.value = '{text_id}'; "
              "s.dispatchEvent(new Event('change')); return s.value; }")  # fmt: skip
        _eval(cli, session, "() => { document.getElementById('start').click(); return true; }")
        time.sleep(clip_s + 1.0)
        _eval(cli, session, "() => { document.getElementById('done').click(); return true; }")
        _eval(
            cli, session,
            f"() => new Promise((r, j) => {{ const t0 = Date.now(); const t = setInterval(() => {{ "
            f"if (document.body.dataset.result === 'ready') {{ clearInterval(t); r(true); }} "
            f"else if (Date.now() - t0 > {int(wait_s * 1000)}) {{ clearInterval(t); "
            f"j(new Error(document.getElementById('status').textContent)); }} }}, 200); }})",
            timeout=int(wait_s) + 30,
        )  # fmt: skip
        return _eval(
            cli, session,
            "() => ({ words: [...document.querySelectorAll('#text-view .w')].map(e => "
            "({ mark: e.dataset.mark, colour: getComputedStyle(e).color, title: e.title })), "
            "accuracy: document.getElementById('fig-accuracy').textContent, "
            "replay: document.getElementById('replay').getAttribute('src'), "
            "requests: performance.getEntriesByType('resource').map(e => e.name).concat([location.href]) })",
        )  # fmt: skip
    finally:
        subprocess.run([cli, f"-s={session}", "close"], cwd=REPO, capture_output=True, timeout=60, check=False)


SIDECAR = FIXTURES / "sidecars" / "f03-t1-misreads-skip.json"


@pytest.fixture
def fake_server(tmp_path: Path) -> Iterator[str]:
    yield from _serve(tmp_path, {"READING_TUTOR_FAKE_ENGINE": str(SIDECAR)})


def test_reading_loop_with_fake_engine(cli: str, fake_server: str, tmp_path: Path):
    side = json.loads(SIDECAR.read_text(encoding="utf-8"))
    got = _read_loop(cli, fake_server, fixture_wav(SIDECAR), side["text_id"], tmp_path, wait_s=30)

    assert [w["mark"] for w in got["words"]] == [m["mark"] for m in side["expected_marks"]]
    assert all(w["colour"] == COLOURS[w["mark"]] for w in got["words"])
    misread = [w for w in got["words"] if w["mark"] == "misread"]
    assert misread and all("чуто" in w["title"] for w in misread)  # heard text on hover
    assert got["accuracy"].startswith("73")  # 8 of 11 correct, no unsure
    assert got["replay"].startswith("/api/attempts/")
    assert all(r.startswith(fake_server) for r in got["requests"]), got["requests"]


@pytest.mark.slow
def test_reading_loop_with_real_turbo(cli: str, tmp_path: Path):
    sidecar = FIXTURES / "sidecars" / "f01-t1-clean.json"
    side = json.loads(sidecar.read_text(encoding="utf-8"))
    server = _serve(tmp_path, {"READING_TUTOR_ENGINE": "whisper-turbo"})
    url = next(server)
    try:
        got = _read_loop(cli, url, fixture_wav(sidecar), side["text_id"], tmp_path, wait_s=240)
    finally:
        server.close()
    assert len(got["words"]) == len(side["expected_marks"])
    assert all(w["colour"] == COLOURS[w["mark"]] for w in got["words"])
    assert all(r.startswith(url) for r in got["requests"]), got["requests"]

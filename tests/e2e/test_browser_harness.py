"""E2E layer, step 1: prove the headless browser harness the app's e2e tests will use.

Headless Playwright Chromium (not the system Chrome) opens a localhost page, gets a fake microphone and records
one second with MediaRecorder. Step 2 points the same harness at the app with an adult fixture WAV
(--use-file-for-fake-audio-capture=tests/fixtures/audio-local/<x>.wav; never recordings/ or data/):
tests/e2e/test_reading_loop.py.

This is "test-verified" only. It is never "laptop-verified": that needs the real laptop microphone (ADR 0002).
"""

from __future__ import annotations

import functools
import http.server
import json
import shutil
import socket
import subprocess
import threading
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest

pytestmark = pytest.mark.e2e

REPO = Path(__file__).resolve().parents[2]
PAGES = Path(__file__).parent / "pages"
CONFIG = REPO / ".playwright" / "cli.config.json"


@pytest.fixture(scope="module")
def cli() -> str:
    path = shutil.which("playwright-cli")
    # Fail, never skip: a skipped e2e layer reads as green (pdfx rule: guarantee the env, never assume it).
    assert path, "playwright-cli not on PATH; install @playwright/cli@0.1.13 globally (docs/SKILLS.md)"
    return path


@pytest.fixture(scope="module")
def server() -> Iterator[str]:
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(PAGES))
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        httpd.shutdown()


def _run(cli: str, session: str, *args: str) -> str:
    out = subprocess.run(
        [cli, f"-s={session}", *args], cwd=REPO, capture_output=True, text=True, timeout=90, check=False
    )
    assert out.returncode == 0, out.stdout + out.stderr
    return out.stdout


def test_config_is_headless_playwright_chromium_with_fake_mic():
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))["browser"]
    assert cfg["browserName"] == "chromium"
    assert "channel" not in cfg.get("launchOptions", {}), "use Playwright's Chromium, not the system Chrome"
    assert cfg["launchOptions"]["headless"] is True
    assert "--use-fake-device-for-media-stream" in cfg["launchOptions"]["args"]
    assert not any("recordings/" in a or "data/" in a for a in cfg["launchOptions"]["args"])


def test_fake_microphone_records_in_headless_chromium(cli: str, server: str):
    session = f"e2e-{uuid.uuid4().hex[:8]}"
    try:
        _run(cli, session, "open", f"--config={CONFIG}", f"{server}/mic.html")
        raw = _run(cli, session, "--raw", "eval", "() => window.recordOneSecond()")
        ua = _run(cli, session, "--raw", "eval", "() => navigator.userAgent")
    finally:
        subprocess.run([cli, f"-s={session}", "close"], cwd=REPO, capture_output=True, timeout=60, check=False)

    result = json.loads(raw)
    assert result["secure"] is True, "localhost must be a secure context"
    assert result["label"].startswith("Fake"), result["label"]
    assert result["mime"].startswith("audio/webm")
    assert result["bytes"] > 0
    assert "HeadlessChrome" in ua

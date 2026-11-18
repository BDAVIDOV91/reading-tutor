"""Regression tests for the privacy review of 2026-11-18 (step 2), one per finding.

1 no-store on every API response; 2 an upload racing Delete all is dropped; 3 no orphan audio when the row insert
fails; 4 no home paths in logs, tracebacks included; 5 device hash keyed by a per-install secret that Delete all
resets; 6 Host-header check and CSP; 8 the stored mime type is from an allow-list.
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
import math
import sqlite3
import struct
import time
import wave
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

import reading_tutor.server.app as appmod
from reading_tutor.server.app import create_app
from reading_tutor.storage.log import Log

pytestmark = pytest.mark.integration

SIDECAR = Path(__file__).resolve().parents[1] / "fixtures" / "sidecars" / "f03-t1-misreads-skip.json"
LABEL = "Иван's AirPods"


def _wav() -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"".join(struct.pack("<h", int(4000 * math.sin(i / 5))) for i in range(16000)))
    return buf.getvalue()


def _upload(c: TestClient, mime: str = "audio/wav") -> httpx.Response:
    return c.post(
        "/api/attempts",
        data={"text_id": "t1-mila-pee", "speaker_kind": "adult_fixture", "speaker_code": "A1",
              "device_label": LABEL, "mime_type": mime, "track_settings": "{}"},  # fmt: skip
        files={"audio": ("r.wav", _wav(), mime)},
    )


def _wait(c: TestClient, aid: str) -> dict:
    for _ in range(200):
        body = c.get(f"/api/attempts/{aid}").json()
        if body["status"] not in ("queued", "running"):
            return body
        time.sleep(0.05)
    raise AssertionError("attempt did not finish")


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("READING_TUTOR_FAKE_ENGINE", str(SIDECAR))
    with TestClient(create_app(), base_url="http://127.0.0.1", raise_server_exceptions=False) as c:
        yield c


def _audio_entries(data: Path) -> list[str]:
    audio = data / "audio"
    return sorted(p.name for p in audio.iterdir()) if audio.exists() else []


# 1 -------------------------------------------------------------------------------------------------------------
def test_api_responses_are_never_cached(client: TestClient):
    aid = _upload(client).json()["attempt_id"]
    _wait(client, aid)
    for path in (f"/api/attempts/{aid}", f"/api/attempts/{aid}/audio", "/api/texts", "/api/config"):
        assert client.get(path).headers.get("cache-control") == "no-store", path


# 2 -------------------------------------------------------------------------------------------------------------
def test_upload_racing_delete_all_is_dropped(client: TestClient, monkeypatch: pytest.MonkeyPatch,
                                             _isolated_data_dir: Path):  # fmt: skip
    real = appmod.derive_wav

    def derive_then_delete_all(*a, **kw):
        out = real(*a, **kw)
        client.app.state.rt.delete_all()
        return out

    monkeypatch.setattr(appmod, "derive_wav", derive_then_delete_all)
    r = _upload(client)
    assert r.status_code == 409
    assert _audio_entries(_isolated_data_dir) == []
    assert client.app.state.rt.log.count("attempts") == 0


# 3 -------------------------------------------------------------------------------------------------------------
def test_failed_row_insert_leaves_no_orphan_audio(client: TestClient, monkeypatch: pytest.MonkeyPatch,
                                                  _isolated_data_dir: Path):  # fmt: skip
    def boom(self, row, **kw):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(Log, "add_attempt", boom)
    assert _upload(client).status_code == 500
    assert _audio_entries(_isolated_data_dir) == []


# 4 -------------------------------------------------------------------------------------------------------------
def test_unhandled_error_logs_no_home_path(client: TestClient, monkeypatch: pytest.MonkeyPatch,
                                           caplog: pytest.LogCaptureFixture):  # fmt: skip
    caplog.set_level(logging.DEBUG)

    def bad_replace(src, dst):
        raise OSError(f"No space left on device: '{dst}'")

    monkeypatch.setattr(appmod.os, "replace", bad_replace)
    r = _upload(client)
    assert r.status_code == 500
    assert str(Path.home()) not in r.text
    assert str(Path.home()) not in caplog.text  # tracebacks included
    assert "OSError" in caplog.text


def test_worker_error_logs_no_home_path(client: TestClient, monkeypatch: pytest.MonkeyPatch,
                                        caplog: pytest.LogCaptureFixture):  # fmt: skip
    caplog.set_level(logging.DEBUG)

    def bad_align(text, heard):
        raise OSError(f"cannot read {Path.home()}/somewhere")

    monkeypatch.setattr(appmod, "align", bad_align)
    aid = _upload(client).json()["attempt_id"]
    _wait(client, aid)
    assert str(Path.home()) not in caplog.text
    assert f"attempt {aid}: processing error OSError" in caplog.text


# 5 -------------------------------------------------------------------------------------------------------------
def test_device_hash_is_keyed_and_reset_by_delete_all(client: TestClient):
    aid = _upload(client).json()["attempt_id"]
    _wait(client, aid)
    h1 = client.app.state.rt.log.get_attempt(aid)["input_device_hash"]
    assert h1 != hashlib.sha256(LABEL.encode()).hexdigest()[:12]  # not guessable from the label alone
    aid2 = _upload(client).json()["attempt_id"]
    _wait(client, aid2)
    assert client.app.state.rt.log.get_attempt(aid2)["input_device_hash"] == h1  # stable within an install

    client.post("/api/delete-all", json={"confirm": True})
    aid3 = _upload(client).json()["attempt_id"]
    _wait(client, aid3)
    assert client.app.state.rt.log.get_attempt(aid3)["input_device_hash"] != h1  # Delete all cuts the link


# 6 -------------------------------------------------------------------------------------------------------------
def test_foreign_host_header_is_refused(client: TestClient):
    assert client.get("/api/texts", headers={"host": "evil.example"}).status_code == 400
    assert client.get("/api/texts", headers={"host": "localhost:8000"}).status_code == 200
    assert client.get("/api/texts", headers={"host": "127.0.0.1:8000"}).status_code == 200


def test_cross_origin_post_is_refused(client: TestClient):
    r = client.post("/api/delete-all", json={"confirm": True}, headers={"origin": "http://evil.example"})
    assert r.status_code == 403


def test_page_has_a_self_only_csp(client: TestClient):
    csp = client.get("/").headers.get("content-security-policy", "")
    assert "default-src 'self'" in csp


# 8 -------------------------------------------------------------------------------------------------------------
def test_unknown_mime_is_not_stored_or_served(client: TestClient):
    aid = _upload(client, mime="text/html").json()["attempt_id"]
    _wait(client, aid)
    assert client.app.state.rt.log.get_attempt(aid)["mime_type"] == "application/octet-stream"
    assert client.get(f"/api/attempts/{aid}/audio").headers["content-type"] == "application/octet-stream"
    assert json.dumps(client.app.state.rt.log.get_attempt(aid)).find("text/html") == -1

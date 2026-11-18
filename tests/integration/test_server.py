"""The local server (step 2 plan, task 7): upload -> attempt row -> derived WAV -> background run -> status ->
marks + score; the child lock; replay of an existing attempt only; Delete all; no transcript text in logs; the
host constant.

Runs with the fake engine (READING_TUTOR_FAKE_ENGINE names a sidecar) and a synthetic sine upload; DATA_DIR is
tmp_path (tests/conftest.py).
"""

from __future__ import annotations

import json
import logging
import math
import struct
import time
import wave
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from reading_tutor import settings
from reading_tutor.server.app import create_app

pytestmark = pytest.mark.integration

SIDECAR = Path(__file__).resolve().parents[1] / "fixtures" / "sidecars" / "f03-t1-misreads-skip.json"
TRACK = {"sampleRate": 48000, "channelCount": 1, "autoGainControl": True, "deviceId": "secret-id", "groupId": "g"}


def _sine_bytes(seconds: float = 2.0, rate: int = 48000) -> bytes:
    import io

    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"".join(struct.pack("<h", int(5000 * math.sin(i / 7))) for i in range(int(seconds * rate))))
    return buf.getvalue()


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, _isolated_data_dir: Path) -> Iterator[TestClient]:
    monkeypatch.setenv("READING_TUTOR_FAKE_ENGINE", str(SIDECAR))
    app = create_app()
    with TestClient(app, base_url="http://127.0.0.1") as c:
        yield c


def _upload(client: TestClient, **over) -> httpx.Response:
    form = {
        "text_id": "t1-mila-pee",
        "speaker_kind": "adult_fixture",
        "speaker_code": "A1",
        "device_label": "Иван's AirPods",
        "mime_type": "audio/wav",
        "track_settings": json.dumps(TRACK),
        **over,
    }
    return client.post("/api/attempts", data=form, files={"audio": ("rec.wav", _sine_bytes(), "audio/wav")})


def _wait(client: TestClient, aid: str, timeout: float = 10.0) -> dict:
    t0 = time.time()
    while time.time() - t0 < timeout:
        body = client.get(f"/api/attempts/{aid}").json()
        if body["status"] not in ("queued", "running"):
            return body
        time.sleep(0.05)
    raise AssertionError("attempt did not finish")


def test_host_is_loopback_only():
    assert settings.HOST == "127.0.0.1"


def test_config_names_the_engine_and_where_audio_goes(client: TestClient):
    cfg = client.get("/api/config").json()
    assert cfg["engine"] == "fake"
    assert cfg["audio_destination"] == "local"
    assert cfg["child_recording_allowed"] is False
    assert cfg["max_seconds"] == 300


def test_texts_lists_builtin_texts(client: TestClient):
    texts = client.get("/api/texts").json()
    ids = [t["id"] for t in texts]
    assert "t1-mila-pee" in ids and "p1-vazov-az-sam-bylgarche" in ids
    t1 = next(t for t in texts if t["id"] == "t1-mila-pee")
    assert t1["text"].startswith("Ето мама")
    assert t1["builtin"] is True


def test_paste_a_text_stores_it_under_data(client: TestClient, _isolated_data_dir: Path):
    r = client.post("/api/texts", json={"title": "Мой", "text": "Котката спи на стола."})
    assert r.status_code == 200
    tid = r.json()["id"]
    assert tid.startswith("u-")
    assert any(t["id"] == tid and t["builtin"] is False for t in client.get("/api/texts").json())
    again = client.post("/api/texts", json={"title": "Мой", "text": "котката спи на стола"})
    assert again.json()["id"] == tid  # same words, same id, no duplicate row
    assert (_isolated_data_dir / "log.sqlite").exists()


def test_paste_rejects_empty_text(client: TestClient):
    assert client.post("/api/texts", json={"title": "x", "text": " — "}).status_code == 422


def test_upload_runs_the_engine_and_returns_marks_and_score(client: TestClient, _isolated_data_dir: Path):
    r = _upload(client)
    assert r.status_code == 200, r.text
    aid = r.json()["attempt_id"]
    body = _wait(client, aid)
    assert body["status"] == "ok"
    expected = json.loads(SIDECAR.read_text(encoding="utf-8"))["expected_marks"]
    assert [w["mark"] for w in body["words"]] == [m["mark"] for m in expected]
    assert [w["heard"] for w in body["words"]] == [m["heard"] for m in expected]
    assert body["words"][0]["surface"] == "Ето"
    s = body["score"]
    assert s["accuracy_F"] == s["accuracy_C"] == round(8 / 11, 2)
    assert s["unsure"] == 0
    assert body["duration_s"] == pytest.approx(2.0, abs=0.05)
    assert body["engine"] == "fake" and body["audio_destination"] == "local"

    d = _isolated_data_dir / "audio" / aid
    assert sorted(p.name for p in d.iterdir()) == ["derived.wav", "original.wav"]
    assert (d / "original.wav").read_bytes() == _sine_bytes()  # the upload is kept untouched
    assert list((_isolated_data_dir / "tmp").iterdir()) == []


def test_attempt_row_keeps_device_class_and_hash_never_the_label(client: TestClient, _isolated_data_dir: Path):
    aid = _upload(client).json()["attempt_id"]
    _wait(client, aid)
    raw = (_isolated_data_dir / "log.sqlite").read_bytes()
    assert "Иван".encode() not in raw
    assert b"secret-id" not in raw  # deviceId / groupId are dropped from track settings
    row = client.app.state.rt.log.get_attempt(aid)
    assert row["input_device_class"] == "bluetooth"
    assert len(row["input_device_hash"]) == 12
    assert row["track_settings"] == {"sampleRate": 48000, "channelCount": 1, "autoGainControl": True}
    assert row["speaker_kind"] == "adult_fixture"
    assert row["core_version"] and row["unsure_threshold"] == 0.8


def test_child_speaker_is_refused_without_the_flag(client: TestClient, _isolated_data_dir: Path):
    r = _upload(client, speaker_kind="child", speaker_code="S1")
    assert r.status_code == 403
    assert not (_isolated_data_dir / "audio").exists() or not any((_isolated_data_dir / "audio").iterdir())


def test_child_speaker_is_accepted_only_with_the_flag(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("READING_TUTOR_FAKE_ENGINE", str(SIDECAR))
    monkeypatch.setenv("READING_TUTOR_CHILD_RECORDING", "1")
    with TestClient(create_app(), base_url="http://127.0.0.1") as c:
        assert c.get("/api/config").json()["child_recording_allowed"] is True
        r = _upload(c, speaker_kind="child", speaker_code="S1")
        assert r.status_code == 200
        _wait(c, r.json()["attempt_id"])


@pytest.mark.parametrize(
    ("field", "value"),
    [("speaker_kind", "parent"), ("speaker_code", "Иван"), ("text_id", "no-such-text"), ("track_settings", "{")],
)
def test_bad_upload_fields_are_refused(client: TestClient, field: str, value: str):
    assert _upload(client, **{field: value}).status_code in (403, 404, 422)


def test_undecodable_upload_is_refused_and_leaves_nothing(client: TestClient, _isolated_data_dir: Path):
    r = client.post(
        "/api/attempts",
        data={"text_id": "t1-mila-pee", "speaker_kind": "adult_fixture", "speaker_code": "A1"},
        files={"audio": ("rec.webm", b"not audio", "audio/webm")},
    )
    assert r.status_code == 422
    assert not any((_isolated_data_dir / "audio").iterdir())
    assert not any((_isolated_data_dir / "tmp").iterdir())


def test_audio_replay_of_an_existing_attempt_only(client: TestClient):
    aid = _upload(client).json()["attempt_id"]
    _wait(client, aid)
    r = client.get(f"/api/attempts/{aid}/audio")
    assert r.status_code == 200
    assert r.content == _sine_bytes()
    assert client.get(f"/api/attempts/{'0' * 32}/audio").status_code == 404
    assert client.get("/api/attempts/..%2F..%2Flog.sqlite/audio").status_code == 404
    assert client.get("/api/attempts/nothex/audio").status_code == 404


def test_unknown_attempt_status_is_404(client: TestClient):
    assert client.get(f"/api/attempts/{'f' * 32}").status_code == 404


def test_delete_all_needs_confirm_and_leaves_a_fresh_db(client: TestClient, _isolated_data_dir: Path):
    aid = _upload(client).json()["attempt_id"]
    _wait(client, aid)
    client.post("/api/texts", json={"title": "x", "text": "мама"})
    assert client.post("/api/delete-all", json={}).status_code == 422
    r = client.post("/api/delete-all", json={"confirm": True})
    assert r.status_code == 200
    assert r.json() == {"deleted": True, "left": ["log.sqlite"]}
    assert sorted(p.name for p in _isolated_data_dir.iterdir()) == ["log.sqlite"]
    assert client.get(f"/api/attempts/{aid}").status_code == 404
    assert all(t["builtin"] for t in client.get("/api/texts").json())
    # the app keeps working after Delete all
    aid2 = _upload(client).json()["attempt_id"]
    assert _wait(client, aid2)["status"] == "ok"


def test_logs_never_carry_text_label_or_home_paths(client: TestClient, caplog: pytest.LogCaptureFixture):
    caplog.set_level(logging.DEBUG)
    aid = _upload(client).json()["attempt_id"]
    _wait(client, aid)
    logged = "\n".join(r.getMessage() for r in caplog.records)
    assert aid in logged  # logs do carry the attempt id
    for forbidden in ("водата", "кожа", "Ето", "Иван", str(Path.home())):
        assert forbidden not in logged


def test_engine_failure_is_shown_and_the_recording_kept(
    monkeypatch: pytest.MonkeyPatch, _isolated_data_dir: Path
):
    from reading_tutor.engines.fake import FakeEngine

    monkeypatch.setenv("READING_TUTOR_FAKE_ENGINE", str(SIDECAR))
    app = create_app(engine_factory=lambda: FakeEngine("", fail=True))
    with TestClient(app, base_url="http://127.0.0.1") as c:
        aid = _upload(c).json()["attempt_id"]
        body = _wait(c, aid)
        assert body["status"] == "failed"
        assert body["words"] == []
        assert (_isolated_data_dir / "audio" / aid / "original.wav").exists()
        assert c.app.state.rt.log.get_runs(aid)[0]["run_status"] == "failed"


def test_index_page_is_served_in_bulgarian(client: TestClient):
    html = client.get("/").text
    assert "Започни четенето" in html and "Готово" in html and "Изтрий всички записи" in html
    assert "http://" not in html.replace("http://localhost", "") and "https://" not in html  # no external loads
    assert client.get("/static/app.js").status_code == 200

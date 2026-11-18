"""`uv run reading-tutor` starts uvicorn on loopback only; the port may change, the host never."""

from __future__ import annotations

import pytest

from reading_tutor import __main__ as entry

pytestmark = pytest.mark.unit


def test_main_binds_loopback(monkeypatch: pytest.MonkeyPatch):
    seen: dict = {}
    monkeypatch.setattr(entry.uvicorn, "run", lambda app, **kw: seen.update(kw, app=app))
    entry.main([])
    assert seen["host"] == "127.0.0.1"
    assert seen["port"] == 8000
    assert seen["app"] == "reading_tutor.server.app:create_app"
    assert seen["factory"] is True


def test_main_port_option(monkeypatch: pytest.MonkeyPatch):
    seen: dict = {}
    monkeypatch.setattr(entry.uvicorn, "run", lambda app, **kw: seen.update(kw))
    entry.main(["--port", "8123"])
    assert (seen["host"], seen["port"]) == ("127.0.0.1", 8123)


def test_there_is_no_host_option():
    with pytest.raises(SystemExit):
        entry.main(["--host", "0.0.0.0"])

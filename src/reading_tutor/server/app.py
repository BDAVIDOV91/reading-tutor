"""The local web app: one page, a small JSON API, and one background worker that runs the engine.

Loopback only (settings.HOST). No CORS, no external requests. Logs carry attempt ids, engine names, statuses
and durations only: never text, never a device label, never a path.
"""

from __future__ import annotations

import json
import logging
import os
import queue
import re
import shutil
import threading
import uuid
from collections.abc import Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from urllib.parse import urlsplit

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from reading_tutor.audio import AudioError, derive_wav, device_class, device_hash
from reading_tutor.core import CORE_VERSION, Mark, align, score, similarity, tokenise
from reading_tutor.core.judge import UNSURE_THRESHOLD
from reading_tutor.core.similarity import SIMILARITY_FN
from reading_tutor.engines import Engine, run_engine
from reading_tutor.engines import make_engine as _make_engine
from reading_tutor.settings import MAX_RECORDING_S, Settings, load_settings
from reading_tutor.storage.files import Layout, delete_all, delete_attempt
from reading_tutor.storage.log import Log
from reading_tutor.texts import Text, load_builtin, pasted_text_id, text_version_hash

log = logging.getLogger("reading_tutor.server")

STATIC = Path(__file__).parent / "static"
MAX_UPLOAD_BYTES = 60 * 1024 * 1024  # 5 minutes of browser audio is a few MB; this is a sanity cap
_ATTEMPT_ID = re.compile(r"^[0-9a-f]{32}$")
_SPEAKER_CODE = re.compile(r"^[A-Z][0-9]{1,2}$")  # a pseudonym such as A1 or S1, never a name
_TRACK_KEYS = {"sampleRate", "sampleSize", "channelCount", "autoGainControl", "noiseSuppression",
               "echoCancellation", "latency"}  # fmt: skip  (deviceId and groupId are identifiers: dropped)
_EXT = {"audio/webm": "webm", "audio/ogg": "ogg", "audio/mp4": "m4a", "audio/wav": "wav", "audio/x-wav": "wav",
        "audio/mpeg": "mp3"}  # fmt: skip


_ALLOWED_HOSTS = {"127.0.0.1", "localhost"}
_CSP = "default-src 'self'; media-src 'self' blob:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"


def _route_label(path: str) -> str:
    """The request path for a log line; it only ever holds an attempt id, but trim anything odd anyway."""
    return re.sub(r"[^A-Za-z0-9/_.-]", "?", path)[:120]


@dataclass
class Runtime:
    settings: Settings
    layout: Layout
    log: Log
    builtin: dict[str, Text]
    engine_factory: Callable[[], Engine]
    engine: Engine | None = None
    status: dict[str, str] = field(default_factory=dict)  # attempt id -> queued | running (in memory only)
    jobs: queue.Queue[str | None] = field(default_factory=queue.Queue)
    lock: threading.RLock = field(default_factory=threading.RLock)  # guards log swaps (Delete all)
    generation: int = 0  # bumped by Delete all; an upload that started before it is dropped

    def delete_all(self) -> list[str]:
        with self.lock:
            self.generation += 1
            self.status.clear()
            self.log = delete_all(self.layout, self.log)
            return sorted(p.name for p in self.layout.root.iterdir())

    def get_engine(self) -> Engine:
        if self.engine is None:
            self.engine = self.engine_factory()
        return self.engine

    def text(self, text_id: str) -> tuple[str, int | None] | None:
        if text_id in self.builtin:
            t = self.builtin[text_id]
            return t.text, t.level
        row = self.log.get_text(text_id)
        return (row["text"], row["level"]) if row else None


def _worker(rt: Runtime) -> None:
    while True:
        aid = rt.jobs.get()
        if aid is None:
            return
        try:
            _process(rt, aid)
        except Exception as e:  # noqa: BLE001 - the worker must survive; the attempt shows as failed
            # Class name only: a traceback or message can carry a path under home (privacy review, finding 4).
            log.error("attempt %s: processing error %s", aid, type(e).__name__)
        finally:
            rt.status.pop(aid, None)


def _process(rt: Runtime, aid: str) -> None:
    with rt.lock:
        attempt = rt.log.get_attempt(aid)
        found = rt.text(attempt["text_id"]) if attempt else None
    if attempt is None or found is None:
        return  # deleted meanwhile
    text = found[0]
    rt.status[aid] = "running"
    engine = rt.get_engine()
    res = run_engine(engine, rt.layout.attempt_dir(aid) / "derived.wav")
    words: list[dict[str, Any]] = []
    if res.run_status == "ok":
        for i, m in enumerate(align(text, res.transcript or "")):
            words.append({
                "word_index": i,
                "expected_token": m.word,
                "engine_mark": str(m.mark),
                "heard_text": m.heard,
                "similarity": round(similarity(m.word, m.heard), 4) if m.heard is not None else None,
            })  # fmt: skip
    run = {
        "engine_id": engine.engine_id,
        "model": engine.model,
        "compute_type": engine.compute_type,
        "prompt_variant": engine.prompt_variant,
        "vad_settings": engine.vad_settings,
        "decoding_settings": engine.decoding_settings,
        "audio_destination": engine.audio_destination,
        "run_status": res.run_status,
        "error_kind": res.error_kind,
        "model_load_s": res.model_load_s,
        "transcribe_wall_s": res.transcribe_wall_s,
        "cold_start": res.cold_start,
        "transcript": res.transcript,
    }
    with rt.lock:
        if rt.log.get_attempt(aid) is None:
            return  # Delete all ran while the engine worked
        rt.log.add_run(aid, run, words)
    log.info(
        "attempt %s: engine=%s status=%s load_s=%s transcribe_s=%s words=%d",
        aid, engine.engine_id, res.run_status, res.model_load_s, res.transcribe_wall_s, len(words),
    )  # fmt: skip


class PastedText(BaseModel):
    title: str = ""
    text: str


class DeleteAll(BaseModel):
    confirm: bool = False


def _figures(marks: list[str], duration_s: float) -> dict[str, Any]:
    s = score(marks, duration_s)
    return {**s, "unsure": sum(m == Mark.UNSURE for m in marks), "duration_s": round(duration_s, 2)}


def create_app(engine_factory: Callable[[], Engine] | None = None) -> FastAPI:
    st = load_settings()
    layout = Layout(st.data_dir)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        layout.ensure()
        rt = Runtime(
            settings=st,
            layout=layout,
            log=Log(layout.db),
            builtin=load_builtin(),
            engine_factory=engine_factory or (lambda: _make_engine(st.engine)),
        )
        app.state.rt = rt
        worker = threading.Thread(target=_worker, args=(rt,), name="attempt-worker", daemon=True)
        worker.start()
        log.info("server ready: engine=%s", st.engine)
        try:
            yield
        finally:
            rt.jobs.put(None)
            worker.join(timeout=5)
            rt.log.close()

    app = FastAPI(title="Reading tutor", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.mount("/static", StaticFiles(directory=STATIC), name="static")

    @app.middleware("http")
    async def guard(request: Request, call_next):
        """Privacy review 2026-11-18: loopback Host only and same-origin writes (finding 6), no caching of any API
        response (finding 1, so Delete all also covers the browser), a self-only CSP (finding 6), and unhandled
        errors logged by class name only, never with a traceback or a path (finding 4)."""
        host = (request.headers.get("host") or "").rsplit(":", 1)[0].strip("[]")
        if host not in _ALLOWED_HOSTS:
            return JSONResponse({"detail": "Непознат адрес."}, status_code=400)
        origin = request.headers.get("origin")
        if request.method not in ("GET", "HEAD") and origin is not None:
            o = urlsplit(origin)
            if o.scheme != "http" or o.hostname not in _ALLOWED_HOSTS:
                return JSONResponse({"detail": "Забранено."}, status_code=403)
        try:
            response = await call_next(request)
        except Exception as e:  # noqa: BLE001
            log.error("%s %s: unhandled %s", request.method, _route_label(request.url.path), type(e).__name__)
            response = JSONResponse({"detail": "Вътрешна грешка. Записите са запазени."}, status_code=500)
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = _CSP
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    def rt() -> Runtime:
        return app.state.rt

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(STATIC / "index.html", media_type="text/html; charset=utf-8")

    @app.get("/api/config")
    def config() -> dict[str, Any]:
        r = rt()
        eng = r.engine
        destination = eng.audio_destination if eng else _engine_destination(r)
        return {
            "engine": r.settings.engine,
            "audio_destination": destination,
            "child_recording_allowed": r.settings.child_recording_allowed,
            "max_seconds": MAX_RECORDING_S,
        }

    @app.get("/api/texts")
    def texts() -> list[dict[str, Any]]:
        r = rt()
        out = [
            {"id": t.id, "level": t.level, "title": t.title, "text": t.text, "source": t.source,
             "licence": t.licence, "builtin": True}
            for t in sorted(r.builtin.values(), key=lambda t: (t.id[0] != "t", t.level or 0, t.id))
        ]  # fmt: skip
        with r.lock:
            pasted = r.log.list_texts()
        out += [
            {"id": p["text_id"], "level": p["level"], "title": p["title"], "text": p["text"], "source": "",
             "licence": "", "builtin": False}
            for p in pasted
        ]  # fmt: skip
        return out

    @app.post("/api/texts")
    def add_text(body: PastedText) -> dict[str, str]:
        if not tokenise(body.text, side="text"):
            raise HTTPException(422, "Текстът няма думи.")
        tid = pasted_text_id(body.text)
        r = rt()
        with r.lock:
            if r.log.get_text(tid) is None:
                r.log.add_text({
                    "text_id": tid, "level": None, "title": body.title.strip()[:80] or "Моят текст",
                    "text": body.text, "text_version_hash": text_version_hash(body.text),
                })  # fmt: skip
        return {"id": tid}

    @app.post("/api/attempts")
    def upload(
        audio: UploadFile = File(...),
        text_id: str = Form(...),
        speaker_kind: str = Form(...),
        speaker_code: str = Form(...),
        device_label: str = Form(""),
        mime_type: str = Form(""),
        track_settings: str = Form("{}"),
    ) -> dict[str, str]:
        r = rt()
        if speaker_kind == "child" and not r.settings.child_recording_allowed:
            raise HTTPException(403, "Записи на деца са изключени до ADR 0003.")
        if speaker_kind not in ("adult_fixture", "child"):
            raise HTTPException(422, "Непознат говорещ.")
        if not _SPEAKER_CODE.fullmatch(speaker_code):
            raise HTTPException(422, "Кодът на говорещия е като A1 или S1.")
        try:
            raw_track = json.loads(track_settings or "{}")
        except json.JSONDecodeError as e:
            raise HTTPException(422, "Невалидни настройки на микрофона.") from e
        track = {k: v for k, v in raw_track.items() if k in _TRACK_KEYS} if isinstance(raw_track, dict) else {}
        found = r.text(text_id)
        if found is None:
            raise HTTPException(404, "Няма такъв текст.")
        text, level = found

        aid = uuid.uuid4().hex
        base_mime = (mime_type or audio.content_type or "").split(";")[0].strip().lower()
        ext = _EXT.get(base_mime, "bin")
        stored_mime = base_mime if base_mime in _EXT else "application/octet-stream"  # finding 8: allow-list
        adir = r.layout.attempt_dir(aid)
        generation = r.generation
        r.layout.ensure()  # Delete all leaves only log.sqlite behind
        staged = r.layout.tmp / f"{aid}.upload"
        try:
            size = 0
            with staged.open("wb") as out:
                while chunk := audio.file.read(1 << 16):
                    size += len(chunk)
                    if size > MAX_UPLOAD_BYTES:
                        raise HTTPException(413, "Записът е твърде голям.")
                    out.write(chunk)
            adir.mkdir(parents=True)
            original = adir / f"original.{ext}"
            os.replace(staged, original)
            derived = derive_wav(original, adir / "derived.wav", tmp_dir=r.layout.tmp)
            # The row goes in under the lock, and only if Delete all has not run since this upload began
            # (finding 2). Any failure from here on removes the audio, so no file outlives its row (finding 3).
            with r.lock:
                if r.generation != generation:
                    raise HTTPException(409, "Записите бяха изтрити по време на качването.")
                r.log.add_attempt(
                    {
                        "text_id": text_id,
                        "text_level": level,
                        "text_version_hash": text_version_hash(text),
                        "speaker_kind": speaker_kind,
                        "speaker_code": speaker_code,
                        "input_device_class": device_class(device_label),
                        "input_device_hash": device_hash(device_label, r.log.device_secret()),
                        "mime_type": stored_mime,
                        "track_settings": track,
                        "audio_duration_s": round(derived.duration_s, 3),
                        "derived_wav_sha256": derived.sha256,
                        "original_ext": ext,
                        "displayed_engine_id": r.settings.engine,
                        "core_version": CORE_VERSION,
                        "similarity_fn": SIMILARITY_FN,
                        "unsure_threshold": UNSURE_THRESHOLD,
                    },
                    attempt_id=aid,
                )
        except AudioError as e:
            shutil.rmtree(adir, ignore_errors=True)
            log.info("attempt %s: audio conversion failed", aid)
            raise HTTPException(422, "Записът не може да се прочете.") from e
        except BaseException:
            shutil.rmtree(adir, ignore_errors=True)
            raise
        finally:
            staged.unlink(missing_ok=True)

        r.status[aid] = "queued"
        r.jobs.put(aid)
        log.info("attempt %s: queued, audio_s=%.1f", aid, derived.duration_s)
        return {"attempt_id": aid}

    def _existing(aid: str) -> dict[str, Any]:
        if not _ATTEMPT_ID.fullmatch(aid):
            raise HTTPException(404, "Няма такъв запис.")
        with rt().lock:
            row = rt().log.get_attempt(aid)
        if row is None:
            raise HTTPException(404, "Няма такъв запис.")
        return row

    @app.get("/api/attempts/{aid}")
    def attempt_status(aid: str) -> dict[str, Any]:
        row = _existing(aid)
        r = rt()
        if aid in r.status:
            return {"attempt_id": aid, "status": r.status[aid]}
        with r.lock:
            runs = r.log.get_runs(aid)
            run = runs[-1] if runs else None
            words = r.log.get_words(run["run_id"]) if run else []
            found = r.text(row["text_id"])
        if run is None:
            return {"attempt_id": aid, "status": "failed", "words": [], "score": None}
        surfaces = [t.surface for t in tokenise(found[0], side="text")] if found else []
        marks = [w["engine_mark"] for w in words]
        return {
            "attempt_id": aid,
            "status": run["run_status"],
            "engine": run["engine_id"],
            "audio_destination": run["audio_destination"],
            "transcribe_s": run["transcribe_wall_s"],
            "duration_s": row["audio_duration_s"],
            "words": [
                {"surface": surfaces[i] if i < len(surfaces) else w["expected_token"], "word": w["expected_token"],
                 "mark": w["engine_mark"], "heard": w["heard_text"]}
                for i, w in enumerate(words)
            ],  # fmt: skip
            "score": _figures(marks, row["audio_duration_s"] or 0.0) if run["run_status"] == "ok" else None,
        }

    @app.get("/api/attempts/{aid}/audio")
    def attempt_audio(aid: str) -> FileResponse:
        row = _existing(aid)
        path = rt().layout.attempt_dir(aid) / f"original.{row['original_ext']}"
        if not path.is_file():
            raise HTTPException(404, "Няма такъв запис.")
        media = (row["mime_type"] or "application/octet-stream").split(";")[0]
        return FileResponse(path, media_type=media)

    @app.delete("/api/attempts/{aid}")
    def remove_attempt(aid: str) -> dict[str, bool]:
        _existing(aid)
        r = rt()
        with r.lock:
            delete_attempt(r.layout, r.log, aid)
        log.info("attempt %s: deleted", aid)
        return {"deleted": True}

    @app.post("/api/delete-all")
    def remove_all(body: DeleteAll) -> dict[str, Any]:
        if not body.confirm:
            raise HTTPException(422, "Потвърдете изтриването.")
        left = rt().delete_all()
        log.info("delete all: done")
        return {"deleted": True, "left": left}

    return app


def _engine_destination(r: Runtime) -> str:
    """The configured engine's audio destination, without loading its model."""
    return r.get_engine().audio_destination

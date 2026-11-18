// Reading tutor page: pick a text, record with MediaRecorder, upload, poll, show the marked text.
// Talks only to this server (same origin). No external requests, no storage in the browser.
"use strict";

const $ = (id) => document.getElementById(id);
const state = { texts: [], config: null, recorder: null, stream: null, chunks: [], stopTimer: null, tick: null };
const MARK_LABEL = {
  correct: "прочетена вярно",
  misread: "прочетена грешно",
  unsure: "не е сигурно",
  skipped: "пропусната",
  not_attempted: "не е стигнато дотук",
};

async function api(path, options) {
  const res = await fetch(path, options);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail || `Грешка ${res.status}`);
  return body;
}

function currentText() {
  return state.texts.find((t) => t.id === $("text-select").value);
}

function showText() {
  const t = currentText();
  $("text-view").textContent = t ? t.text : "";
}

async function loadTexts(selectId) {
  state.texts = await api("/api/texts");
  const sel = $("text-select");
  sel.innerHTML = "";
  for (const t of state.texts) {
    const opt = document.createElement("option");
    opt.value = t.id;
    opt.textContent = t.builtin ? `${t.level}. ${t.title}` : `${t.title} (свой текст)`;
    sel.appendChild(opt);
  }
  if (selectId) sel.value = selectId;
  showText();
}

async function init() {
  state.config = await api("/api/config");
  $("engine-name").textContent = state.config.engine;
  $("engine-dest").textContent = state.config.audio_destination === "local" ? "остава на този компютър (local)" : state.config.audio_destination;
  $("speaker").querySelector('option[value="child"]').disabled = !state.config.child_recording_allowed;
  await loadTexts();
}

function setStatus(msg) {
  $("status").textContent = msg;
}

function speakerCode(kind) {
  return kind === "child" ? "S1" : "A1";
}

async function start() {
  $("results").hidden = true;
  setStatus("");
  showText();
  try {
    state.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch (e) {
    setStatus("Няма достъп до микрофона.");
    return;
  }
  const recorder = new MediaRecorder(state.stream);
  state.recorder = recorder;
  state.chunks = [];
  recorder.ondataavailable = (e) => e.data.size && state.chunks.push(e.data);
  recorder.onstop = upload;
  recorder.start(1000);
  $("start").hidden = true;
  $("done").hidden = false;
  $("setup").hidden = true;
  const t0 = Date.now();
  $("timer").hidden = false;
  state.tick = setInterval(() => {
    const s = Math.floor((Date.now() - t0) / 1000);
    $("timer").textContent = `Запис: ${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
  }, 250);
  state.stopTimer = setTimeout(() => {
    setStatus("Записът спря след 5 минути.");
    stop();
  }, state.config.max_seconds * 1000);
}

function stop() {
  clearTimeout(state.stopTimer);
  clearInterval(state.tick);
  $("done").hidden = true;
  $("timer").hidden = true;
  if (state.recorder && state.recorder.state !== "inactive") state.recorder.stop();
}

async function upload() {
  const track = state.stream.getAudioTracks()[0];
  const label = track ? track.label : "";
  const settings = track ? track.getSettings() : {};
  state.stream.getTracks().forEach((t) => t.stop());
  const mime = state.recorder.mimeType || "audio/webm";
  const blob = new Blob(state.chunks, { type: mime });
  state.chunks = []; // keep no copy of the recording in the page once it is packed for upload
  const kind = $("speaker").value;
  const form = new FormData();
  form.append("audio", blob, "recording");
  form.append("text_id", $("text-select").value);
  form.append("speaker_kind", kind);
  form.append("speaker_code", speakerCode(kind));
  form.append("device_label", label); // the server keeps only a class and a short hash
  form.append("mime_type", mime);
  form.append("track_settings", JSON.stringify(settings));
  setStatus("Обработва се…");
  try {
    const { attempt_id } = await api("/api/attempts", { method: "POST", body: form });
    await poll(attempt_id);
  } catch (e) {
    setStatus(e.message);
    resetControls();
  }
}

async function poll(id) {
  for (;;) {
    const body = await api(`/api/attempts/${id}`);
    if (body.status === "queued" || body.status === "running") {
      await new Promise((r) => setTimeout(r, 1000));
      continue;
    }
    showResults(id, body);
    return;
  }
}

function pct(x) {
  return x == null ? "–" : Math.round(x * 100);
}

function range(a, b, unit) {
  if (a == null && b == null) return "–";
  return a === b ? `${a}${unit}` : `${a}–${b}${unit}`;
}

function showResults(id, body) {
  resetControls();
  if (body.status !== "ok") {
    setStatus(body.status === "timeout" ? "Разпознаването отне твърде дълго. Записът е запазен." : "Разпознаването не успя. Записът е запазен.");
    return;
  }
  setStatus("");
  const view = $("text-view");
  view.innerHTML = "";
  body.words.forEach((w, i) => {
    const span = document.createElement("span");
    span.className = `w ${w.mark}`;
    span.dataset.mark = w.mark;
    span.dataset.index = String(i);
    span.textContent = w.mark === "unsure" ? `${w.surface}?` : w.surface;
    const heard = w.heard != null && (w.mark === "misread" || w.mark === "unsure") ? ` · чуто: „${w.heard}“` : "";
    span.title = `${MARK_LABEL[w.mark]}${heard}`;
    span.addEventListener("click", () => ($("heard-line").textContent = `${w.surface}: ${span.title}`));
    view.appendChild(span);
    view.appendChild(document.createTextNode(" "));
  });
  const s = body.score;
  const unsure = s.unsure ? `, ${s.unsure} несигурни` : "";
  $("fig-accuracy").textContent = `${range(pct(s.accuracy_F), pct(s.accuracy_C), " %")}${unsure}`;
  $("fig-wcpm").textContent = range(s.wcpm_F, s.wcpm_C, "");
  $("fig-wpm").textContent = s.raw_wpm == null ? "–" : String(s.raw_wpm);
  $("fig-time").textContent = `${s.duration_s} s`;
  $("replay").src = `/api/attempts/${id}/audio`;
  $("results").hidden = false;
  document.body.dataset.result = "ready";
}

function resetControls() {
  $("start").hidden = false;
  $("done").hidden = true;
  $("setup").hidden = false;
}

async function pasteText() {
  const text = $("paste-text").value;
  try {
    const { id } = await api("/api/texts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: $("paste-title").value, text }),
    });
    $("paste-msg").textContent = "Текстът е добавен.";
    await loadTexts(id);
  } catch (e) {
    $("paste-msg").textContent = e.message;
  }
}

async function deleteAll() {
  if (!confirm("Да се изтрият ли всички записи, оценки и поставени текстове? Това не може да се върне.")) return;
  try {
    await api("/api/delete-all", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ confirm: true }),
    });
    $("delete-msg").textContent = "Всички записи са изтрити.";
    $("results").hidden = true;
    $("replay").removeAttribute("src");
    await loadTexts();
  } catch (e) {
    $("delete-msg").textContent = e.message;
  }
}

$("text-select").addEventListener("change", showText);
$("start").addEventListener("click", start);
$("done").addEventListener("click", stop);
$("again").addEventListener("click", () => {
  $("results").hidden = true;
  delete document.body.dataset.result;
  showText();
});
$("paste-add").addEventListener("click", pasteText);
$("delete-all").addEventListener("click", deleteAll);
init().catch((e) => setStatus(e.message));

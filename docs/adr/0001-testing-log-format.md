---
status: accepted
date: 2026-11-18
---

# Testing log: SQLite plus files, five word states, engine and parent marks kept apart

The prototype's only output that answers the brief is the testing log, and its shape decides which numbers can
ever be computed: a field missed now cannot be recovered from old attempts. We store it as one SQLite file plus
audio files under the gitignored `data/` directory, with one row per expected word per engine run, the engine's
marking written once and never changed, and the parent's marking stored separately per attempt and word. The
field list is the `engine-evaluator` proposal (owner decision Q9, 2026-11-18); storage is owner decision Q10.

## Word states

| State | Meaning |
|---|---|
| `correct` | Read as written (after normalisation). A self-correction whose last attempt is right is `correct`. |
| `misread` | Something else was read; the heard text is kept. |
| `skipped` | Passed over, with reading continuing after it. |
| `unsure` | A near match on a long word (rule below). A measuring aid for the prototype, not a product state. |
| `not_attempted` | After the last word reached (early stop). Excluded from accuracy and recall. |

**Unsure rule.** After normalisation an exact match is `correct`. An expected word of 4 letters or fewer must
match exactly, otherwise `misread`. A word of 5 letters or more with rapidfuzz
`Levenshtein.normalized_similarity(expected, heard) >= 0.80` is `unsure`, otherwise `misread`. 0.80 is an untuned
starting value, to be tuned on adult deliberate-mistake fixtures. The similarity sits behind one function so it
can be swapped. A digit heard for a number word is compared through a small digit lookup.

Repeats and insertions are not errors. Self-correction: the last attempt at a word wins.

## Fields

**Attempt** (one per reading):

- `attempt_id`, `recorded_at`, `schema_version`
- `text_id`, `text_level`, `text_version_hash` (hash of the normalised token list, so an edited text is never
  pooled with its old version)
- `speaker_kind` {`child`, `adult_fixture`}; `speaker_code` (pseudonym such as `S1`, never a name)
- `input_device_class` {`builtin`, `usb`, `bluetooth`, `headset`, `unknown`} plus `input_device_hash` (short hash
  of the browser's label), never the raw label: Bluetooth labels often carry a person's name ("<Name>'s
  AirPods"). A unit test with an invented label covers this.
- `mime_type`, `track_settings` (sample rate, channels, AGC, noise suppression, echo cancellation); optional
  `room_condition` {quiet, noisy}, `mic_distance` {near, far}
- `audio_duration_s`, `derived_wav_sha256` (proves every engine got the same audio)
- `whole_attempt_reviewed` (bool), `reviewed_at`
- `displayed_engine_id`: whose colours the parent saw while marking (anchoring check)
- `core_version`, `similarity_fn`, `unsure_threshold`

**Engine run** (one per attempt and engine):

- `run_id`, `attempt_id`, `engine_id`, `model` (name and revision), `compute_type`
- `prompt_variant` {`none`, `target_text`}: prompted and unprompted runs are never pooled
- VAD settings (silence gap in ms, threshold); decoding settings (beam, temperature,
  `condition_on_previous_text`, no-speech threshold)
- `audio_destination` {`local`, `cloud:<provider>:<region>`}
- `run_status` {`ok`, `failed`, `timeout`}: failed runs never drop out silently
- `model_load_s` and `transcribe_wall_s` kept apart; `cold_start`; optional peak RAM
- the raw transcript, stored locally only

**Word** (one per expected word per run, including `skipped` and `not_attempted` words):

- `word_index`, `expected_token` (normalised)
- `engine_mark`: one of the five states, written once, never overwritten
- `heard_text`, `similarity` (local only; for tuning)

**Parent mark** (one per attempt and word, shared by all engines):

- `parent_mark` {`correct`, `misread`, `skipped`, `not_attempted`, `self_corrected_correct`}
- `parent_mark_source` {`explicit_tap`, `default_on_review`}: shows which "correct" marks come only from the
  parent ticking "reviewed"

Adult fixtures may also carry a hand-written `reference_transcript`, so the aligner can be scored without an engine.

## Metrics

Computed from reviewed attempts only, excluding words the parent marked `not_attempted`. "Parent says wrong" =
`misread` or `skipped`. "App flags" = `misread` or `skipped`, with `unsure` counted as flagged in **variant F** and
as correct in **variant C**; every metric is reported in both variants.

- Recall = TP / (TP + FN); precision = TP / (TP + FP)
- False flags per 100 = 100 × FP / words the parent marked correct
- Unsure per 100 = 100 × unsure / words
- Agreement = matching marks / words (reported, never a gate)
- Speed = median `transcribe_wall_s` / `audio_duration_s`
- Per attempt: accuracy = correct / attempted; WCPM; raw WPM (attempted words per minute)

## Storage

- `data/log.sqlite`: attempts, runs, words, parent marks. `schema_version` with forward-only migrations.
- `data/audio/<attempt_id>/original.<ext>` (untouched upload) and `derived.wav` (16 kHz mono, what every engine
  reads).
- `data/exports/`: CSV exports. By default an export holds ids, marks, counts and timings only: no `heard_text`,
  no transcript. A test asserts the export's column list. Copies moved out of `data/exports/` (for example to
  Downloads) are not covered by "Delete all", and the owner is told so.
- `data/tmp/`: every temporary and conversion file (upload staging, original → `derived.wav`). Nothing is
  written outside `data/`.
- File and path names carry the attempt id only, never a name or age.

**Delete all** closes the database and removes `log.sqlite` with its `-wal`, `-shm` and `-journal` side files,
`data/audio/`, `data/exports/` and `data/tmp/`, then verifies `data/` holds nothing but a fresh empty database.
Row deletes leave text in SQLite's free pages, so deleting one attempt runs with `PRAGMA secure_delete=ON`. A test
with fixture files covers both (privacy review 2026-11-18).

## Additions in schema v1 (step 2, owner-approved 2026-11-18)

Implementation added fields and tables; none renames or drops a field above.

- `texts` table: pasted texts (`text_id` = `u-` + version hash, title, text, hash). Child-adjacent content, so
  Delete all removes it with the database.
- `install` table: the per-install secret that keys `input_device_hash` (HMAC-SHA256 of the label, first 12 hex);
  an unkeyed hash of "<Name>'s AirPods" can be reversed by guessing names (privacy review 2026-11-18, finding 5).
  Delete all replaces it, which also cuts the link between old and new device hashes.
- `attempts.original_ext`: the extension of the untouched upload (`original.<ext>`); `mime_type` holds an
  allow-listed base type only.
- `runs.error_kind`: the exception class name of a `failed` or `timeout` run, never its message.
- `runs.model` carries the pinned revision (`<model>@<12-hex revision>`).

## Considered options

- **Parent correction overwrites the engine mark**: rejected; every metric would be lost.
- **Rows only for flagged words**: rejected; skipped words drop out of the denominator.
- **JSON files per attempt**: rejected; cross-attempt reports need joins, and migrations are harder to enforce.

## Consequences

- Adding a field later is cheap (migration), but attempts recorded before it lack it; the list is deliberately
  complete now.
- Transcripts and heard text never appear in a report; the aggregate report prints counts only.

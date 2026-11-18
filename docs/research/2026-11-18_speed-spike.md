# Speed spike: local Bulgarian STT on this laptop

Date: 2026-11-18. Plan step 0b. **Adult speed only, this laptop (M1).** Transcript quality is not judged here.

## Setup

- **Machine:** M1 laptop, 4 cores, 7.2 GB RAM (1.6 GB free, 4.8 GB available at the start), no GPU.
- **Audio:** one recording of the owner (adult) reading a public-domain passage slowly, partly syllable by
  syllable, with pauses. 150.0 s, 16 kHz mono WAV, laptop microphone. Kept in `spike/audio/` (gitignored, not
  synced to M2).
- **Run:** `spike/run_all.sh`. One model per fresh process, one after another. `HF_HUB_OFFLINE=1`, `uv --frozen
  --offline`, cold start (model loaded once per run). Single run per engine: no repeats, so there is no spread.
- **Settings:**
  - Whisper: `faster-whisper` 1.2.1, CPU int8, `language="bg"`, no prompt, `condition_on_previous_text=False`,
    VAD on with `min_silence_duration_ms=1000`.
  - CTC: `transformers` 5.23 with CPU torch 2.15, float32, plain processor (no LM), `chunk_length_s=15` with
    stride (4, 2).
  - Parakeet: `onnx-asr`, int8, Silero VAD, language auto-detected.
- **Pass figure (plan Q2, fixed before measuring):** transcription ≤ 1× real time = interactive; ≤ 5× = offline
  batch only (still evaluated); slower, or peak RSS > 3.0 GB, or OOM = not viable on this laptop.

## Results

| Engine | Model | Load | Transcribe | RTF | Peak RSS | Verdict |
|---|---|---|---|---|---|---|
| whisper-small | `Systran/faster-whisper-small` | 3.9 s | 37.7 s | 0.25 | 0.65 GB | **interactive** |
| whisper-medium | `Systran/faster-whisper-medium` | 9.1 s | 59.1 s | 0.39 | 1.63 GB | **interactive** |
| whisper-turbo | `deepdml/faster-whisper-large-v3-turbo-ct2` | 6.5 s | 55.5 s | 0.37 | 1.70 GB | **interactive** |
| ctc-bg | `anuragshas/wav2vec2-large-xls-r-300m-bg` | 10.1 s | 446.6 s | 2.98 | 2.02 GB | **offline batch only** |
| parakeet-v3 | `nemo-parakeet-tdt-0.6b-v3` | 11.7 s | 30.9 s | 0.21 | 1.52 GB | **interactive** |

- RTF = transcribe time / audio length. Peak RSS is from `/usr/bin/time -v`, and Python's own `ru_maxrss` agrees
  within 3 %.
- Anonymous RSS after transcription (excluding mmap'd weights): small 0.47 GB, medium 1.29 GB, turbo 1.12 GB,
  CTC 0.30 GB, Parakeet 1.45 GB.
- All five fit under the 3.0 GB figure. Turbo, expected to be the risk, peaked at 1.70 GB.

Raw JSON lines: `spike/out/*.time` and the session log (not committed: they sit beside the transcripts).

## What this supports

- Whisper small, medium and turbo, and Parakeet v3, run a slow 2.5-minute read in under 1 minute on this
  laptop. A child waits about 30 to 60 s after reading. Speed does not force a smaller model.
- The CTC model is offline-batch only as configured: 7.4 minutes for 2.5 minutes of audio. It stays in the
  evaluation (finding 6) and runs on saved attempts after the child is done.

## What it does not support

- Nothing about accuracy, and nothing about children: adult voice, one speaker, one recording.
- One cold run per engine on a laptop with other work open; expect some spread on repeats.
- **Word counts differ a lot between engines** for the same audio (small 51, medium 43, turbo 53, CTC 37,
  Parakeet 23 words). Parakeet's 23 suggests it dropped parts of the slow, paused read: either its VAD
  segmentation or language auto-detection (forcing Bulgarian is unverified). This is a quality question for the
  adult deliberate-mistake fixtures (R12), not a speed result, and is the first thing to check before Parakeet
  is wired as an engine.

## Cheap speed-ups not tried

- CTC: int8 dynamic quantisation, an ONNX export, or longer chunks. Only worth trying if CTC earns its place on
  the fixtures (finding 8).
- Whisper: `beam_size=1` (greedy). It changes decoding, so it would be a labelled engine setting, not a free win.

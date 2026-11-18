---
name: reading-fixtures
description: How to create and use test fixtures for the reading tutor — invented transcripts for alignment and scoring tests, and adult-recorded audio that imitates how a young child reads. Use when writing alignment, scoring or engine tests, when a bug needs a reproduction, or when asked to test with a real recording.
---

# Reading fixtures

Real children's recordings and transcripts never become fixtures. Two kinds of fixture replace them.

## 1. Text fixtures (alignment and scoring)

Hand-written `expected text → transcript → expected marking` cases. They need no audio and no engine, so they
are the default for every alignment and scoring test.

- Cases live in `tests/cases/<behaviour>.json` (`normalise`, `judge`, `align`, `score`), language-neutral, run
  by `tests/unit/test_<behaviour>.py`. The rules they encode and the owner's approvals: `tests/cases/README.md`.
- Get cases from the `bulgarian-reading-specialist` agent, or write them and have it review them. A new rule
  (not just a new case) needs the owner's yes before RED, and a line in `tests/cases/README.md`.
- A bug in marking becomes a new row first (RED), then the fix. Run it with
  `uv run pytest tests/unit/test_align.py -k <case-id>`; the full gate is the `run-tests` skill.
- Write Latin look-alike letters and combining marks as `\uXXXX` escapes, so the file shows what it tests.
- To reproduce a problem seen with a child, the owner describes it in words ("she repeated the second word
  twice and it went orange") and the case is written from that description with invented text.

## 2. Audio fixtures (engines, end to end)

Recorded by an adult (the owner), reading a sample text the way a child might. The WAVs live in
`tests/fixtures/audio-local/<id>.wav`: **local only**, gitignored and excluded from the M2 sync (step 2 plan S2),
because they are still a real person's voice. Record with
`ffmpeg -f pulse -i default -ac 1 -ar 16000 -t 30 tests/fixtures/audio-local/<id>.wav`. Every clip has a line in
`tests/fixtures/FIXTURES.md`; a test that needs a WAV fails when it is missing.

Each recording has a committed sidecar `tests/fixtures/sidecars/<id>.json`:

| Field | Content |
|---|---|
| `id`, `text_id`, `kind` | `f03-t1-misreads-skip`; a built-in text id (`texts/`); `clean`, `syllables`, `misreads_skip`, `repeats_selfcorrection` |
| `speaker`, `recorded_by`, `device` | always `adult`; `owner`; the microphone |
| `audio` | `audio-local/<id>.wav` |
| `instructions`, `planned` | what to read and how; the deliberate mistakes in words |
| `reference_transcript` | what the adult actually says, syllables as separate words |
| `expected_marks` | `[{word, mark, heard}]`, the same shape as `tests/cases/align.json` |

`tests/unit/test_fixture_sidecars.py` checks that `expected_marks == align(text, reference_transcript)`, so the
aligner is scored on hand-written transcripts with no engine. The deliberate mistakes are what make a fixture
useful: they show whether an engine reports a misreading or silently "corrects" it. The e2e fake engine returns a
sidecar's `reference_transcript`.

Minimum set per sample text level: one clean read, one slow syllable-by-syllable read, one with two
substitutions and one skip, one with repeats and a self-correction, one with background noise.

Audio fixtures are never `git add`ed. Before a clip is used, the owner confirms it is an adult voice with no child
audible in the background. Keep files short (under 30 seconds) and mono.

## Limits

Results on these fixtures are "test-verified" on an adult voice. They say nothing certain about children; only
the owner's device tests do (`engine-eval` skill).

---
paths:
  - "**/*audio*"
  - "**/*record*"
  - "**/*stt*"
  - "**/*transcri*"
  - "**/*storage*"
  - "**/*attempt*"
  - "**/engines/**"
---

# Child data: audio, storage and STT client code

The recordings are of the owner's own children, ages 6 to 8. Voice of a minor is personal data under GDPR.

## Audio capture and storage
- Audio is written only under `recordings/` or `data/` (both gitignored), on the owner's laptop or device.
- File names carry an attempt id and a timestamp. No child name, age or other identifier in a file name or path.
- "Delete all recordings" removes the audio files **and** every transcript and score derived from them, then
  verifies the directories are empty. A test covers this with fixture files.
- The server binds to the home network only. No public URL, no tunnel service (ngrok, cloudflared, localtunnel).

## STT clients
- Every engine sits behind one interface and declares where audio goes: `local` or `cloud:<provider>:<region>`.
  The UI shows that value next to the engine name.
- A cloud engine needs an ADR and the owner's explicit yes before its first call with a real recording. Use an EU
  region where one exists and switch off every retention, logging and training option the provider offers; the
  ADR cites the provider's page for each setting.
- Keys are read from `.env` on the server side. The browser never receives a key.

## Logs, errors, tests
- Logs and error messages carry attempt ids, durations and engine names. Never transcript text, never audio
  bytes, never a file path under a user's home.
- Tests use invented text and adult-recorded or synthetic audio in `tests/fixtures/`. Never copy a file from
  `recordings/` or `data/` into a fixture, a prompt or a bug report.
- Claude does not read, list the contents of, play or transcribe anything under `recordings/` or `data/`. To
  debug a real attempt, the owner describes it or reproduces it with an adult voice.

## Accuracy claims
- An engine accuracy number states its sample: how many recordings, which speakers (adult or child), which
  texts. A number measured on adult fixtures is never reported as accuracy on children.

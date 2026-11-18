# reading-tutor

Bulgarian reading tutor prototype: a child reads a text aloud, the app transcribes, aligns and marks each word.
Brief: `docs/PROTOTYPE_BRIEF.md`; working rules: `CLAUDE.md`.

## Run (laptop browser, ADR 0002)

```bash
uv sync                       # dev + engines groups (Whisper turbo through faster-whisper)
uv run reading-tutor          # http://localhost:8000, loopback only
```

Data (recordings, the SQLite log) goes to `data/`, gitignored and never synced. „Изтрий всички записи“ on the
page removes all of it. Only adult voices until ADR 0003 (child lock).

Tests: the `run-tests` skill (`.claude/skills/run-tests/SKILL.md`).

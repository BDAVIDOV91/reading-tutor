---
name: run-tests
description: Commands, layers and the coverage floor for the reading tutor test suite. Use before running tests, claiming a suite is green, adding a test module, or at a checkpoint.
---

# Run tests

Three layers, mirroring pdf_data_extractor_v2's unit / integration / e2e groups. Every test module sets exactly one
`pytestmark = pytest.mark.<layer>` matching its directory; `tests/unit/test_layer_guard.py` goes red otherwise,
because an untagged module silently drops out of `-m <layer>` runs.

| Layer | Directory | What belongs there | Command |
|---|---|---|---|
| unit | `tests/unit/` | Core logic from `tests/cases/*.json`, invariants, import boundary (R11). No network, no browser. | `uv run pytest -m unit` |
| integration | `tests/integration/` | Modules together; later the SQLite log and local engines on adult fixtures. | `uv run pytest -m integration` |
| e2e | `tests/e2e/` | Headless Playwright Chromium via `playwright-cli` with a fake microphone. | `uv run pytest -m e2e` |

## Full gate (checkpoint, before a commit that touches `src/` or `tests/`)

```bash
uv run pytest --cov --cov-fail-under=95; echo "rc=$?"
```

- Quote the summary line (passed/failed counts) and `rc`. A green claim without both is not a claim.
- The 95 % floor (statements and branches of `src/reading_tutor`) lives in this command, not in `pyproject.toml`,
  so single-test runs stay unburdened (same choice as pdfx).
- Save RED and GREEN output for the checkpoint's Evidence line.

## Rules

- **e2e fails, never skips**, when `playwright-cli` or its Chromium is missing: a skipped layer reads as green.
  Install: `npm i -g @playwright/cli@0.1.13 && playwright-cli install-browser chromium`.
- Fake-microphone audio comes only from `tests/fixtures/audio/` (adult voice), listed in
  `tests/fixtures/FIXTURES.md`. When a test passes `--use-file-for-fake-audio-capture`, it checks that the path
  resolves under `tests/fixtures/` (an allow-list, not a deny-list).
- A headless e2e pass is "test-verified". "laptop-verified" needs the real laptop microphone (ADR 0002).
- Runs stay on M1. The M2 sync (`ops/remote-shell/mutagen.yml`) is file sync only; there is no remote-shell
  wrapper or sync proof in this repo, so M2 test results are not evidence.
- The spike (`spike/`) has its own uv project and no tests (plan Q4); the root suite never imports it.

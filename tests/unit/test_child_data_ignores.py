"""Child data stays off git and off M2 even when a file lands outside data/ (privacy review 2026-11-18, finding 4).

Also guards the order in mutagen.yml: the `!tests/fixtures/**` exception must come before the secret patterns,
so a key or .env under tests/fixtures is still excluded (mutagen and git: last match wins).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

REPO = Path(__file__).resolve().parents[2]
MUTAGEN = REPO / "ops" / "remote-shell" / "mutagen.yml"
GITIGNORE = REPO / ".gitignore"

CHILD_DATA = ["recordings", "data", "*.sqlite", "*.sqlite-*", "*.db", "exports", "tmp", "*.wav", "*.webm"]
SECRETS = [".env*", "*.pem", "*.key"]
FIXTURE_EXCEPTION = "!tests/fixtures/**"
AUDIO_EXT = {".wav", ".mp3", ".m4a", ".ogg", ".oga", ".opus", ".webm", ".flac", ".aac", ".3gp"}


def _mutagen_patterns() -> list[str]:
    return re.findall(r"^\s*-\s*'([^']+)'", MUTAGEN.read_text(encoding="utf-8"), flags=re.MULTILINE)


def _gitignore_patterns() -> list[str]:
    lines = GITIGNORE.read_text(encoding="utf-8").splitlines()
    return [ln.strip().rstrip("/") for ln in lines if ln.strip() and not ln.startswith("#")]


@pytest.mark.parametrize("pattern", CHILD_DATA + SECRETS)
def test_mutagen_excludes(pattern: str):
    assert pattern in _mutagen_patterns()


@pytest.mark.parametrize("pattern", CHILD_DATA)
def test_gitignore_excludes(pattern: str):
    assert pattern in _gitignore_patterns()


def test_fixture_exception_cannot_reinclude_secrets():
    p = _mutagen_patterns()
    assert all(p.index(FIXTURE_EXCEPTION) < p.index(s) for s in SECRETS)


LOCAL_FIXTURE_AUDIO = "tests/fixtures/audio-local"  # the owner's voice: local only, never committed or synced


def test_gitignore_excludes_local_fixture_audio_after_the_exception():
    """Git: last match wins, so the re-exclude must come after `!tests/fixtures/**`."""
    p = _gitignore_patterns()
    assert f"{LOCAL_FIXTURE_AUDIO}/**" in p
    assert p.index(f"{LOCAL_FIXTURE_AUDIO}/**") > p.index("!tests/fixtures/**")


def test_mutagen_excludes_local_fixture_audio_after_the_exception():
    p = _mutagen_patterns()
    assert LOCAL_FIXTURE_AUDIO in p
    assert p.index(LOCAL_FIXTURE_AUDIO) > p.index(FIXTURE_EXCEPTION)


def test_every_audio_fixture_is_listed_as_adult_or_synthetic():
    """Finding 5: tests/fixtures/** is committable, so every audio file there needs a manifest line."""
    fixtures = REPO / "tests" / "fixtures"
    manifest = fixtures / "FIXTURES.md"
    listed = manifest.read_text(encoding="utf-8") if manifest.exists() else ""
    audio = [p for p in fixtures.rglob("*") if p.suffix.lower() in AUDIO_EXT] if fixtures.exists() else []
    missing = [str(p.relative_to(REPO)) for p in audio if f"`{p.relative_to(fixtures)}`" not in listed]
    assert not missing, f"audio fixtures without a FIXTURES.md line (adult or synthetic, recorded by whom): {missing}"

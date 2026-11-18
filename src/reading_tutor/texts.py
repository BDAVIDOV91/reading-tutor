"""Built-in reading texts (texts/<id>.json, committed) and text version hashes.

A text's version hash is taken over its normalised token list (ADR 0001), so punctuation, case and stress edits
keep the hash, and any change to the words gives a new one: an edited text is never pooled with its old version.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from reading_tutor.core import tokenise

TEXTS_DIR = Path(__file__).resolve().parents[2] / "texts"
_FIELDS = {"id", "level", "title", "text", "source", "licence"}


@dataclass(frozen=True)
class Text:
    id: str
    level: int | None
    title: str
    text: str
    source: str
    licence: str


def text_version_hash(text: str) -> str:
    tokens = [t.norm for t in tokenise(text, side="text")]
    return hashlib.sha256("\n".join(tokens).encode("utf-8")).hexdigest()[:16]


def pasted_text_id(text: str) -> str:
    """A pasted text's id: `u-` + its version hash, so the same words always get the same id."""
    return f"u-{text_version_hash(text)}"


def load_builtin(directory: Path = TEXTS_DIR) -> dict[str, Text]:
    texts: dict[str, Text] = {}
    for path in sorted(directory.glob("*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        if set(raw) != _FIELDS:
            raise ValueError(f"{path.name}: fields must be {sorted(_FIELDS)}")
        if raw["id"] != path.stem:
            raise ValueError(f"{path.name}: id {raw['id']!r} does not match the file name")
        if not tokenise(raw["text"], side="text"):
            raise ValueError(f"{path.name}: text has no words")
        texts[raw["id"]] = Text(**raw)
    return texts

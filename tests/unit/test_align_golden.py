"""Stored-results differential for `align` (aligner step 5, owner decision D6, 2026-11-19).

`tests/cases/align_golden.json` holds N invented reading tails and the marks core 0.5.0 gave them (`marks_050`),
generated once by `regenerate()` before the step-5 change. It is a snapshot, known-wrong marks included, not a
definition of correct: tests/cases/align.json is that.

The test reads only the file. Every input must give exactly its 0.5.0 marks, or, when the input is listed in
`changes`, exactly the `after` marks recorded there (so the list records reviewed updates and exempts nothing).
On top, against `marks_050`, four never-rules hold for every input:

1. no new `skipped`;
2. no `correct` -> anything else, no `unsure` -> misread / skipped / not_attempted;
   (exception to 1 and 2: a `by-design` change whose `ref` names a reviewed align.json row, e.g. a stutter that
   rule 6 marks misread, owner 2026-11-19);
3. no new `misread` whose heard form is not a single heard token or is below REATTEMPT_MIN similarity to its word;
4. a `misread` that disappears must be listed with class `missed-misread` (the count is printed).

This guards against unexpected behaviour changes. It is not proof of correctness: the evidence for step 5 is the
larger in-memory differential described in the plan.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

import pytest

from reading_tutor.core.align import REATTEMPT_MIN, align
from reading_tutor.core.normalise import tokenise
from reading_tutor.core.similarity import similarity

pytestmark = pytest.mark.unit

CASES = Path(__file__).parent.parent / "cases"
GOLDEN = CASES / "align_golden.json"
CLASSES = {"fix", "by-design", "missed-misread"}

SEED = 20261119
N = 200
TEXTS: tuple[str, ...] = (
    "ето мама и баба мила пее тото пие вода коза пасе",  # t1
    "в езерото плуват три бели патици виж иво патиците искат хляб казва ани",  # a t5 slice
)
VOWELS = "аеиоуъя"
REDUCTIONS = {"о": "у", "е": "и", "а": "ъ"}
FILLERS = ("ъъъ", "ммм", "а")
PARENT = ("браво", "да", "добре")


def _marks(text: str, heard: str) -> list[list]:
    return [[m.word, str(m.mark), m.heard] for m in align(text, heard)]


# --- generator: used once to write the file; the test never calls it ---------------------------------------


def _reduce(w: str, rng: random.Random) -> str:
    idx = [i for i, c in enumerate(w) if c in REDUCTIONS]
    if not idx:
        return w
    i = rng.choice(idx)
    return w[:i] + REDUCTIONS[w[i]] + w[i + 1 :]


def _drop(w: str, rng: random.Random) -> str:
    if len(w) < 3:
        return w
    i = rng.randrange(1, len(w))
    return w[:i] + w[i + 1 :]


def _syllables(w: str) -> list[str]:
    out: list[str] = []
    cur = ""
    for c in w:
        cur += c
        if c in VOWELS:
            out.append(cur)
            cur = ""
    if cur:
        if out:
            out[-1] += cur
        else:
            out = [cur]
    return out


def _sloppy(w: str, rng: random.Random, prefix: list[str]) -> list[str]:
    """One sloppy attempt at w: reduction, dropped letter, or syllable split (sometimes with an echo inside)."""
    op = rng.random()
    if op < 0.4:
        return [_reduce(w, rng)]
    if op < 0.7:
        return [_drop(w, rng)]
    sy = _syllables(_reduce(w, rng) if rng.random() < 0.5 else w)
    if len(sy) > 1 and rng.random() < 0.3:
        k = rng.randrange(1, len(sy))
        sy = sy[:k] + [rng.choice(prefix)] + sy[k:]
    return sy


def _tail(rng: random.Random, forced: bool) -> tuple[str, str]:
    t: list[str] = rng.choice(TEXTS).split()
    n = len(t)
    p = rng.randint(1, n - 1)
    h = list(t[:p])
    shape = rng.random()
    if shape < 0.15 and p >= 2:  # glued anchor
        i = rng.randrange(0, p - 1)
        h = h[:i] + [h[i] + h[i + 1]] + h[i + 2 :]
    elif shape < 0.3:  # stutter after an exact word
        i = rng.randrange(0, p)
        if len(t[i]) > 2:
            h.insert(i + 1, t[i][:-1])
    elif shape < 0.4 and p >= 2:  # restart 1-4 words back
        b = max(0, p - rng.randint(1, 4))
        h.extend(t[b:p])
    nxt = p
    ops = rng.randint(1 if forced else 0, 3)
    sloppy_done = False
    for _ in range(ops):
        op = rng.random()
        w = t[nxt] if nxt < n else rng.choice(t)
        if (forced and not sloppy_done) or op < 0.55:
            h.extend(_sloppy(w, rng, t[:p]))
            nxt += 1
            sloppy_done = True
        elif op < 0.7:
            h.append(rng.choice(FILLERS))
        elif op < 0.8:
            h.append(rng.choice(PARENT))
        else:  # an echo in the middle of the tail
            h.append(rng.choice(t[:p]))
    echoes = rng.randint(1 if forced else 0, 2)
    for _ in range(echoes):
        h.append(rng.choice(t[: max(p, min(nxt, n))]))
    return " ".join(t), " ".join(h)


def regenerate(path: Path = GOLDEN) -> None:
    """Write the snapshot with the current core. Refuses to overwrite: the file is the 0.5.0 baseline."""
    if path.exists():
        raise FileExistsError(f"{path} exists; it is the 0.5.0 snapshot and is never regenerated")
    rng = random.Random(SEED)
    inputs = []
    for i in range(N):
        text, heard = _tail(rng, forced=i % 2 == 0)
        inputs.append({"input_id": f"g{i:03d}", "text": text, "heard": heard, "marks_050": _marks(text, heard)})
    data = {
        "behaviour": "align_golden",
        "note": (
            f"Generated snapshot of core 0.5.0 marks (seed {SEED}, N {N}), known-wrong marks included; not a "
            "definition of correct. Invented tails over t1 and a t5 slice. See tests/unit/test_align_golden.py."
        ),
        "inputs": inputs,
        "changes": [],
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


# --- the test ----------------------------------------------------------------------------------------------


def _load() -> dict:
    data = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert data["behaviour"] == "align_golden"
    return data


def _align_ids() -> set[str]:
    return {c["id"] for c in json.loads((CASES / "align.json").read_text(encoding="utf-8"))["cases"]}


def test_golden_file_is_well_formed():
    data = _load()
    ids = [i["input_id"] for i in data["inputs"]]
    assert len(ids) == len(set(ids)) == N
    align_ids = _align_ids()
    changed = [c["input_id"] for c in data["changes"]]
    assert len(changed) == len(set(changed)), "an input is listed twice in changes"
    for c in data["changes"]:
        assert c["input_id"] in ids, c
        assert c["class"] in CLASSES, c
        if c["class"] != "fix":
            assert c["ref"] in align_ids, f"{c['input_id']}: class {c['class']} must name an align.json row"


def test_regenerate_refuses_to_overwrite():
    with pytest.raises(FileExistsError):
        regenerate(GOLDEN)


def _never_rule_breaks(inp: dict, now: list[list], change: dict | None) -> list[str]:
    heard_tokens = {tok.norm for tok in tokenise(inp["heard"], side="heard")}
    by_design = bool(change and change["class"] == "by-design")
    out = []
    for (word, old, old_heard), (_, new, new_heard) in zip(inp["marks_050"], now, strict=True):
        if new == "skipped" and old != "skipped" and not by_design:
            out.append(f"rule 1 new skipped: {word}")
        if old == "correct" and new != "correct" and not by_design:
            out.append(f"rule 2 lost credit: {word} correct -> {new} ({new_heard})")
        if old == "unsure" and new not in ("correct", "unsure") and not by_design:
            out.append(f"rule 2 lost credit: {word} unsure -> {new} ({new_heard})")
        if new == "misread" and (old, old_heard) != ("misread", new_heard):
            if new_heard not in heard_tokens or similarity(word, new_heard) < REATTEMPT_MIN:
                out.append(f"rule 3 misread from a joined or far form: {word} ({new_heard})")
        if old == "misread" and new != "misread" and not (change and change["class"] == "missed-misread"):
            out.append(f"rule 4 unlisted missed misread: {word} ({old_heard}) -> {new}")
    return out


@pytest.mark.parametrize(
    ("old", "new", "change", "rule"),
    [
        (["коза", "not_attempted", None], ["коза", "skipped", None], None, "rule 1"),
        (["коза", "correct", "коза"], ["коза", "misread", "куза"], None, "rule 2"),
        (["коза", "unsure", "кузаа"], ["коза", "not_attempted", None], None, "rule 2"),
        (["коза", "not_attempted", None], ["коза", "misread", "кузапее"], None, "rule 3"),
        (["коза", "not_attempted", None], ["коза", "misread", "пее"], None, "rule 3"),
        (["коза", "misread", "кза"], ["коза", "not_attempted", None], None, "rule 4"),
        (["коза", "correct", "коза"], ["коза", "skipped", None], {"class": "by-design"}, None),
        (["коза", "correct", "коза"], ["коза", "misread", "куза"], {"class": "by-design"}, None),
        (["коза", "misread", "кза"], ["коза", "not_attempted", None], {"class": "missed-misread"}, None),
        (["коза", "not_attempted", None], ["коза", "misread", "кза"], None, None),
    ],
)
def test_never_rules_fire_on_synthetic_marks(old, new, change, rule):
    """The snapshot may hold no changed input, so each never-rule is shown to fire on a hand-made diff."""
    inp = {"heard": "куза кза пее", "marks_050": [old]}
    breaks = _never_rule_breaks(inp, [new], change)
    if rule is None:
        assert breaks == []
    else:
        assert len(breaks) == 1 and breaks[0].startswith(rule), breaks


def test_marks_match_snapshot_or_listed_change_and_never_rules_hold():
    data = _load()
    changes = {c["input_id"]: c for c in data["changes"]}
    failures = []
    for inp in data["inputs"]:
        now = _marks(inp["text"], inp["heard"])
        change = changes.get(inp["input_id"])
        want = change["after"] if change else inp["marks_050"]
        if now != want:
            diff = [(o, n) for o, n in zip(want, now, strict=True) if o != n]
            failures.append(f"{inp['input_id']} {inp['heard']!r}: expected {diff}")
        failures += [f"{inp['input_id']} {inp['heard']!r}: {b}" for b in _never_rule_breaks(inp, now, change)]
    missed = sum(1 for c in data["changes"] if c["class"] == "missed-misread")
    print(f"golden: {len(data['inputs'])} inputs, {len(changes)} listed changes, {missed} missed-misread")
    assert not failures, "\n".join(failures)

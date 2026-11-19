"""Align an engine transcript with the text and mark every text word.

Two passes (rules: tests/cases/README.md, owner-approved 2026-11-18 and 2026-11-19):

1. **Anchors.** A longest-common-subsequence DP picks the most text words that the transcript matches exactly
   (``judge.equivalent``: exact, digit lookup, article pair), where 1 to 5 consecutive heard tokens may be joined
   ("ма ма" -> "мама"), and one heard token may anchor two glued text words ("милапее", rule 18). On equal word
   counts the anchors covering more heard tokens win; ties then prefer later heard tokens, because the last
   attempt at a word wins. Anchors after the last far jump that cover at most 2 text words are strays after a
   stop and are dropped (rule 16).
2. **Gaps.** Between two anchors, a small cost DP places the leftover heard tokens. Advancing is free; a misread
   costs 1 - similarity; a skipped text word costs 1 (a skipped line costs the words skipped); an insertion
   (filler, extra word) costs 0.6; a re-attempt of the word just read, or an exact repeat of a recently read word,
   costs 0.1; one heard token with an exact part may cover two words (near glue, rule 18). After the last anchor,
   stopping is free (the remaining words are not attempted) and joined fragments need similarity >= 0.5.

Every attempt becomes an event (heard position, text word, heard form); the last event per word is judged.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from reading_tutor.core.judge import VOWELS, Mark, equivalent, judge_detail
from reading_tutor.core.normalise import tokenise
from reading_tutor.core.similarity import similarity

MAX_JOIN = 5  # syllable fragments joined into one word (owner 2026-11-18)
REATTEMPT_MIN = 0.5  # untuned: below this a following heard word is an insertion, not a re-attempt
REPEAT_WINDOW = 12  # how far back an exact repeat may jump
GLUE_MIN_LEN = 3  # untuned (rule 18): a glued heard token is at least this long
GLUE_MIN_EXACT = 3  # untuned (rule 18): near glue needs an exact part at least this long
AHEAD_WINDOW = 4  # untuned: an exact match to one of this many upcoming anchored words is an early attempt at it
STRAY_JUMP = 5  # untuned (rule 16): more text words than this between two anchors is a jump
STRAY_MAX_WORDS = 2  # untuned (rule 16): at most this many anchored text words after the last jump are strays

_SKIP = 1.0
_INSERT = 0.6
_REATTEMPT = 0.1
_JOIN = 0.01  # per extra fragment, so a join is used only when it helps
_TIE = 1e-9

# Pure functions on short strings: caching keeps a messy 2-minute read well under a second.
_eq = lru_cache(maxsize=65536)(equivalent)
_sim = lru_cache(maxsize=65536)(similarity)


@dataclass(frozen=True)
class WordMark:
    word: str
    mark: Mark
    heard: str | None
    surface: str = ""
    via: str = ""  # core only, never logged: "reduction" or "glue" when that rule decided the mark


@dataclass(frozen=True)
class _Event:
    pos: int  # index of the first heard token of the attempt
    word: int  # text word index
    heard: str
    mark: Mark | None = None  # set when the pass that made the event already decided the mark
    via: str = ""


@dataclass(frozen=True)
class _Anchor:
    """Text words text_start..text_end (inclusive) matched exactly by heard tokens j0..j1 (exclusive).

    `parts` holds each text word's own heard form, in order."""

    text_start: int
    text_end: int
    j0: int
    j1: int
    parts: tuple[str, ...]


@lru_cache(maxsize=262144)
def _glue(a: str, b: str, tok: str) -> tuple[str, str] | None:
    """Rule 18 exact glue: `tok` is text words a + b written as one word. Returns each word's own part, or None.

    Split points are bounded to len(a) - 2 .. len(a) + 2 (article and digit forms). A shared consonant may merge
    ("братича" for брат тича): then both words are exact and the parts are the words themselves."""
    if len(tok) < GLUE_MIN_LEN:  # the caller's first-letter check is exact: equivalent() keeps the first letter
        return None
    for cut in range(max(1, len(a) - 2), min(len(tok) - 1, len(a) + 2) + 1):
        x, y = tok[:cut], tok[cut:]
        if _eq(a, x) and _eq(b, y):
            return x, y
    if a and b and a[-1] == b[0] and a[-1] not in VOWELS and tok == a + b[1:]:
        return a, b
    return None


def _anchors(t: list[str], h: list[str]) -> list[_Anchor]:
    """Exact matches, monotone, as many text words as possible; on a tie, the ones covering more heard tokens
    (so "то пла та" anchors топлата as one word, not то). A heard token (or joined fragments) may anchor two
    consecutive text words when it is the two glued together (rule 18)."""
    n, m = len(t), len(h)
    word = m + 1  # one matched text word outweighs any number of covered tokens
    joins = [["".join(h[j : j + span]) for span in range(min(MAX_JOIN, m - j) + 1)] for j in range(m + 1)]
    best = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            v = max(best[i + 1][j], best[i][j + 1])
            for span in range(1, len(joins[j])):
                tok = joins[j][span]
                if _eq(t[i], tok):
                    v = max(v, word + span + best[i + 1][j + span])
                if i + 1 < n and (tok[0] == t[i][0] or tok[0].isdigit()) and _glue(t[i], t[i + 1], tok):
                    v = max(v, 2 * word + span + best[i + 2][j + span])
            best[i][j] = v

    out: list[_Anchor] = []
    i = j = 0
    while i < n and j < m and best[i][j] > 0:
        if best[i][j + 1] == best[i][j]:  # skip this heard token: keep the word for a later attempt
            j += 1
            continue
        step = None
        for span in range(1, len(joins[j])):  # single words first, so separate anchors win a tie with glue
            if _eq(t[i], joins[j][span]) and word + span + best[i + 1][j + span] == best[i][j]:
                step = _Anchor(i, i, j, j + span, (joins[j][span],))
                break
        if step is None and i + 1 < n:
            for span in range(1, len(joins[j])):
                parts = _glue(t[i], t[i + 1], joins[j][span])
                if parts and 2 * word + span + best[i + 2][j + span] == best[i][j]:
                    step = _Anchor(i, i + 1, j, j + span, parts)
                    break
        if step is None:
            i += 1
            continue
        out.append(step)
        i, j = step.text_end + 1, step.j1
    return out


def _one_letter_dropped(part: str, word: str) -> bool:
    """True when `part` and `word` differ by exactly one inserted or dropped letter (Levenshtein 1, length +-1)."""
    short, long_ = sorted((part, word), key=len)
    if len(long_) - len(short) != 1:
        return False
    return any(long_[:k] + long_[k + 1 :] == short for k in range(len(long_)))


@lru_cache(maxsize=65536)
def _near_glue(a: str, b: str, tok: str) -> tuple[str, str, int] | None:
    """Rule 18 near glue: one heard token covers text words a, b, with an exact part (>= GLUE_MIN_EXACT letters)
    for one word and the rest close to the other (similarity >= REATTEMPT_MIN). Returns (part for a, part for b,
    index of the inexact word: 0 or 1), or None. Split points are bounded like `_glue`."""
    if len(tok) < GLUE_MIN_LEN:
        return None
    found: list[tuple[float, str, str, int]] = []
    for cut in range(max(1, len(a) - 2), min(len(tok) - 1, len(a) + 2) + 1):  # exact prefix for a
        x, y = tok[:cut], tok[cut:]
        if len(x) >= GLUE_MIN_EXACT and _eq(a, x) and _sim(b, y) >= REATTEMPT_MIN:
            found.append((_sim(b, y), x, y, 1))
    for cut in range(max(1, len(tok) - len(b) - 2), min(len(tok) - 1, len(tok) - len(b) + 2) + 1):  # exact suffix
        x, y = tok[:cut], tok[cut:]
        if len(y) >= GLUE_MIN_EXACT and _eq(b, y) and _sim(a, x) >= REATTEMPT_MIN:
            found.append((_sim(a, x), x, y, 0))
    if not found:
        return None
    _, x, y, inexact = max(found, key=lambda f: f[0])
    return x, y, inexact


def _drop_stray_tail(anchors: list[_Anchor], n_text: int) -> list[_Anchor]:
    """Rule 16 (owner 2026-11-19, fixture f06): after the reader stops, a stray heard word can exactly match a text
    word far ahead and turn every word in between into `skipped`. When the anchors after the last jump (more than
    STRAY_JUMP text words between two anchors; the text start counts as an anchor) cover at most STRAY_MAX_WORDS
    text words and not the text's last word, they are dropped and their tokens go back to the tail gap. Repeated
    until nothing changes. Errs toward not_attempted (harmless) over skipped (shames the child)."""
    out = list(anchors)
    while out:
        last_jump = None
        prev_end = -1
        for idx, a in enumerate(out):
            if a.text_start - prev_end - 1 > STRAY_JUMP:
                last_jump = idx
            prev_end = a.text_end
        if last_jump is None:
            break
        run = out[last_jump:]
        words = sum(a.text_end - a.text_start + 1 for a in run)
        if words > STRAY_MAX_WORDS or run[-1].text_end == n_text - 1:
            break
        out = out[:last_jump]
    return out


def _gap(
    t: list[str],
    h: list[str],
    words: range,
    heard: range,
    prev_word: int | None,
    next_word: int | None,
    tail: bool,
) -> list[_Event]:
    """Place heard tokens `heard` against text words `words` between two anchors. Returns the attempt events."""
    k_n, x_n = len(words), len(heard)
    inf = float("inf")
    # cost[k][x]: cheapest way to finish from gap word k and gap heard token x
    cost = [[inf] * (x_n + 1) for _ in range(k_n + 1)]
    step: list[list[tuple | None]] = [[None] * (x_n + 1) for _ in range(k_n + 1)]

    for k in range(k_n, -1, -1):
        for x in range(x_n, -1, -1):
            if x == x_n and (k == k_n or tail):
                cost[k][x] = 0.0  # done; in the tail, words left are not attempted
                continue
            options: list[tuple[float, int, tuple]] = []  # (cost, priority, step)
            if k < k_n:
                options.append((_SKIP + cost[k + 1][x], 4, ("skip",)))
            if x < x_n:
                tok = h[heard[x]]
                if k < k_n:
                    w = words[k]
                    for span in range(1, min(MAX_JOIN, x_n - x) + 1):
                        joined = "".join(h[heard[x] : heard[x] + span])
                        if tail and span > 1 and _sim(t[w], joined) < REATTEMPT_MIN:
                            continue  # tail join floor (2026-11-19): fillers after a stop never join into a word
                        c = 1 - _sim(t[w], joined) + _JOIN * (span - 1)
                        options.append((c + cost[k + 1][x + span], 0, ("match", w, span, joined)))
                    if k + 1 < k_n:
                        near = _near_glue(t[w], t[w + 1], tok)
                        if near:
                            c = 1 - _sim(t[w] + t[w + 1], tok) + _JOIN
                            options.append((c + cost[k + 2][x + 1], 0, ("glue", w, near)))
                prev = words[k - 1] if k > 0 else prev_word
                nxt = next_word if k == k_n else None
                sim_prev = _sim(t[prev], tok) if prev is not None else -1.0
                sim_next = _sim(t[nxt], tok) if nxt is not None else -1.0
                ahead = next_word is not None and any(
                    _eq(t[w], tok) for w in range(next_word, min(len(t), next_word + AHEAD_WINDOW))
                )
                if ahead:  # an exact early attempt at an upcoming word (a phrase repeat): never a re-attempt
                    options.append((_REATTEMPT + cost[k][x + 1], 1, ("again", None)))
                elif max(sim_prev, sim_next) >= REATTEMPT_MIN:
                    target = prev if sim_prev >= sim_next else None  # None: an earlier attempt at the next anchor
                    options.append((_REATTEMPT + cost[k][x + 1], 1, ("again", target)))
                g = words[k] if k < k_n else (next_word if next_word is not None else len(t))
                for r in range(g - 1, max(-1, g - 1 - REPEAT_WINDOW), -1):
                    if _eq(t[r], tok):
                        options.append((_REATTEMPT + cost[k][x + 1], 2, ("again", r)))
                        break
                options.append((_INSERT + cost[k][x + 1], 3, ("insert",)))
            if options:
                c, _, s = min(options, key=lambda o: (round(o[0] / _TIE) * _TIE, o[1]))
                cost[k][x], step[k][x] = c, s

    events: list[_Event] = []
    k = x = 0
    while not (x == x_n and (k == k_n or tail)):
        s = step[k][x]
        assert s is not None
        if s[0] == "skip":
            k += 1
        elif s[0] == "match":
            _, w, span, joined = s
            events.append(_Event(heard[x], w, joined))
            k, x = k + 1, x + span
        elif s[0] == "glue":
            _, w, (x_part, y_part, inexact) = s
            for off, part in enumerate((x_part, y_part)):
                mark = None
                if off == inexact and _one_letter_dropped(part, t[w + off]):
                    mark = Mark.UNSURE  # an engine artefact: exception to the <= 4-letter exact rule (ADR 0001)
                events.append(_Event(heard[x], w + off, part, mark, "glue"))
            k, x = k + 2, x + 1
        elif s[0] == "again":
            if s[1] is not None:
                events.append(_Event(heard[x], s[1], h[heard[x]]))
            x += 1
        else:  # insert
            x += 1
    return events


def align(text: str, heard: str) -> list[WordMark]:
    text_tokens = tokenise(text, side="text")
    t = [tok.norm for tok in text_tokens]
    h = [tok.norm for tok in tokenise(heard, side="heard")]

    anchors = _drop_stray_tail(_anchors(t, h), len(t))
    events = [
        _Event(a.j0, a.text_start + k, part, via="glue" if len(a.parts) > 1 else "")
        for a in anchors
        for k, part in enumerate(a.parts)
    ]

    start = _Anchor(-1, -1, 0, 0, ())
    end = _Anchor(len(t), len(t), len(h), len(h), ())
    bounds = [start, *anchors, end]
    for a, b in zip(bounds, bounds[1:], strict=False):
        is_tail = b is end
        events += _gap(
            t,
            h,
            words=range(a.text_end + 1, b.text_start),
            heard=range(a.j1, b.j0),
            prev_word=a.text_end if a.text_end >= 0 else None,
            next_word=None if is_tail else b.text_start,
            tail=is_tail,
        )

    last: dict[int, _Event] = {}
    for ev in sorted(events, key=lambda e: e.pos):
        last[ev.word] = ev
    reached = max(last, default=-1)

    marks: list[WordMark] = []
    for i, tok in enumerate(text_tokens):
        ev = last.get(i)
        if ev is not None:
            if ev.mark is not None:
                mark, via = ev.mark, ev.via
            else:
                mark, judged_via = judge_detail(tok.norm, ev.heard)
                via = judged_via or ev.via
            marks.append(WordMark(tok.norm, mark, ev.heard, tok.surface, via))
        elif i < reached:
            marks.append(WordMark(tok.norm, Mark.SKIPPED, None, tok.surface))
        else:
            marks.append(WordMark(tok.norm, Mark.NOT_ATTEMPTED, None, tok.surface))
    return marks

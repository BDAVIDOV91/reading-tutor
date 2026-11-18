"""Align an engine transcript with the text and mark every text word.

Two passes (rules: tests/cases/README.md, owner-approved 2026-11-18):

1. **Anchors.** A longest-common-subsequence DP picks the most text words that the transcript matches exactly
   (``judge.equivalent``: exact, digit lookup, article pair), where 1 to 5 consecutive heard tokens may be joined
   ("ма ма" -> "мама"). Ties prefer later heard tokens, because the last attempt at a word wins.
2. **Gaps.** Between two anchors, a small cost DP places the leftover heard tokens. Advancing is free; a misread
   costs 1 - similarity; a skipped text word costs 1 (a skipped line costs the words skipped); an insertion
   (filler, extra word) costs 0.6; a re-attempt of the word just read, or an exact repeat of a recently read word,
   costs 0.1. After the last anchor, stopping is free: the remaining words are not attempted.

Every attempt becomes an event (heard position, text word, heard form); the last event per word is judged.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from reading_tutor.core.judge import Mark, equivalent, judge
from reading_tutor.core.normalise import tokenise
from reading_tutor.core.similarity import similarity

MAX_JOIN = 5  # syllable fragments joined into one word (owner 2026-11-18)
REATTEMPT_MIN = 0.5  # untuned: below this a following heard word is an insertion, not a re-attempt
REPEAT_WINDOW = 12  # how far back an exact repeat may jump
_MIN_GLUED_STEM = 2  # rule 15: "брати" -> "брат" + "и"; a one-letter stem is never split
AHEAD_WINDOW = 4  # untuned: an exact match to one of this many upcoming anchored words is an early attempt at it

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


@dataclass(frozen=True)
class _Event:
    pos: int  # index of the first heard token of the attempt
    word: int  # text word index
    heard: str


def _anchors(t: list[str], h: list[str]) -> list[tuple[int, int, int]]:
    """Exact matches (text index, heard start, heard end), monotone, as many as possible."""
    n, m = len(t), len(h)
    best = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            v = max(best[i + 1][j], best[i][j + 1])
            for span in range(1, min(MAX_JOIN, m - j) + 1):
                if _eq(t[i], "".join(h[j : j + span])):
                    v = max(v, 1 + best[i + 1][j + span])
            best[i][j] = v

    out: list[tuple[int, int, int]] = []
    i = j = 0
    while i < n and j < m and best[i][j] > 0:
        if best[i][j + 1] == best[i][j]:  # skip this heard token: keep the word for a later attempt
            j += 1
            continue
        for span in range(1, min(MAX_JOIN, m - j) + 1):
            if _eq(t[i], "".join(h[j : j + span])) and 1 + best[i + 1][j + span] == best[i][j]:
                out.append((i, j, j + span))
                i, j = i + 1, j + span
                break
        else:
            i += 1
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
                        c = 1 - _sim(t[w], joined) + _JOIN * (span - 1)
                        options.append((c + cost[k + 1][x + span], 0, ("match", w, span, joined)))
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
        elif s[0] == "again":
            if s[1] is not None:
                events.append(_Event(heard[x], s[1], h[heard[x]]))
            x += 1
        else:  # insert
            x += 1
    return events


def _split_glued_i(t: list[str], h: list[str]) -> list[str]:
    """Rule 15 (owner 2026-11-18, fixtures f06-f08): an engine writes 'брат ѝ' as 'брати'. When a text word is
    followed by a stand-alone и, a heard token equal to that word + и is split back into the two."""
    stems = {t[i] for i in range(len(t) - 1) if t[i + 1] == "и" and len(t[i]) >= _MIN_GLUED_STEM}
    out: list[str] = []
    for tok in h:
        if tok.endswith("и") and tok[:-1] in stems:
            out += [tok[:-1], "и"]
        else:
            out.append(tok)
    return out


def align(text: str, heard: str) -> list[WordMark]:
    text_tokens = tokenise(text, side="text")
    t = [tok.norm for tok in text_tokens]
    h = _split_glued_i(t, [tok.norm for tok in tokenise(heard, side="heard")])

    anchors = _anchors(t, h)
    events = [_Event(j0, i, "".join(h[j0:j1])) for i, j0, j1 in anchors]

    bounds = [(-1, 0, 0)] + anchors + [(len(t), len(h), len(h))]
    for (ia, _, ja_end), (ib, jb_start, _) in zip(bounds, bounds[1:], strict=False):
        is_tail = ib == len(t)
        events += _gap(
            t,
            h,
            words=range(ia + 1, ib),
            heard=range(ja_end, jb_start),
            prev_word=ia if ia >= 0 else None,
            next_word=None if is_tail else ib,
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
            marks.append(WordMark(tok.norm, judge(tok.norm, ev.heard), ev.heard, tok.surface))
        elif i < reached:
            marks.append(WordMark(tok.norm, Mark.SKIPPED, None, tok.surface))
        else:
            marks.append(WordMark(tok.norm, Mark.NOT_ATTEMPTED, None, tok.surface))
    return marks

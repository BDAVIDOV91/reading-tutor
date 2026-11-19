# Core test cases

Language-neutral JSON, one file per behaviour. They define what "correct" means, so a port of the core to another
language is checked by the same files. Drafted by `bulgarian-reading-specialist` from invented text only, approved
by the owner on 2026-11-18. Never add a real child's words here.

| File | Function under test |
|---|---|
| `normalise.json` | `normalise_token`, `tokenise(text, side=...)` |
| `judge.json` | `judge(expected, heard)`: the mark for one final attempt |
| `align.json` | `align(text, heard)`: one mark per text word |
| `score.json` | `score(marks, duration_s)` |
| `align_golden.json` | `align`: a **generated snapshot of core 0.5.0 marks** on 200 invented tails, known-wrong marks included; not a definition of correct. Reviewed changes are listed in it (`tests/unit/test_align_golden.py`) |

## Rules the cases encode

Settled in grilling (Q5 to Q7) and in ADR 0001:

- Exact match after normalisation = `correct`. Expected word of ≤ 4 letters: exact only, else `misread`. ≥ 5
  letters: `Levenshtein.normalized_similarity` ≥ 0.80 = `unsure`, else `misread` (0.80 untuned).
- Words after the last word reached = `not_attempted`; skipped = passed over with reading continuing after it.
- Accuracy = correct / attempted; WCPM; raw WPM; every figure in variant C (unsure as correct) and F (unsure as
  flagged). Repeats and insertions are not errors; self-correction: the last attempt wins.

Owner decisions on the specialist's proposals (2026-11-18):

1. **Article endings**: `-ът`/`-а` and `-ят`/`-я` are equivalent (they sound the same), both directions, only when
   the stem before the ending has ≥ 3 letters (so `път` is never an article form).
2. **Hyphens**: split only on the heard side. On the text side a hyphen (U+002D, U+2010, U+2011) between letters
   joins the parts into one word (`ма-ма` → `мама`, `по-голям` → `поголям`); en dash, em dash and minus sign
   split on both sides.
3. **Digit + article**: a heard `2-те` stays one token `2те` and matches `двете`.
4. **Fragments**: 2 to 5 consecutive heard tokens may be joined into one word.

The specialist's own gap rules, accepted as starting values:

1. Latin look-alikes map to Cyrillic only inside a token that also has a Cyrillic letter. The table is
   case-sensitive and runs before casefold: upper `A B C E H K M O P T X Y` → `А В С Е Н К М О Р Т Х У`; lower
   `a c e o p x y k` → `а с е о р х у к`.
2. Normalisation keeps only letters and digits after stripping U+0300 and U+0301 (so `й` survives, `ѝ` → `и`,
   `ѐ` → `е`), then casefolds.
3. Surface form keeps attached punctuation; a token empty after normalising is dropped from both lists.
4. `normalise_token("ма-ма")` = `мама`; splitting is `tokenise`'s job.
5. Exact matches (including digit lookup, article equivalence and joined fragments) are anchors; the words between
   anchors are aligned locally.
6. A heard word after an attempt is a re-attempt of that word when similarity ≥ 0.5 (untuned), otherwise an
   insertion. If it is closer to the next anchored word, it is an earlier attempt at that word.
7. A heard word equal to a recently read text word is a repeat; if that word's earlier attempt was wrong, the
   repeat replaces it (last attempt wins).
8. `heard` holds the normalised final attempt: joined fragments without spaces, digits as digits. `null` for
   `skipped` and `not_attempted`.
9. The 4-letter rule counts the expected word's letters.
10. Score: fractions 0..1 rounded to 2 decimals; `skipped` counts as attempted; nothing attempted → accuracy and
    unsure_per_100 null, rates 0; duration 0 → rates null.
11. Fillers (`ъъъ`) are ordinary insertions.
12. Digit lookup 0 to 10 (cardinal, feminine/neuter, plural and personal forms) plus the `-те`/`-та`/`-мата`
    definite forms; ordinals are left out.
13. Six or more fragments are not joined.
14. A heard word that exactly matches one of the next 4 anchored text words (`AHEAD_WINDOW`, untuned) is an early
    attempt at that word (a phrase repeat), never a re-attempt of the previous word, even when it is close to it
    (`тото пие тото пие` after `пее`). Owner 2026-11-18, found by fixture f04; case
    `phrase-repeat-near-twin-of-previous-word`. Core version 0.2.0.
15. When a text word is followed by a stand-alone `и` (from `ѝ` or `и`), a heard token equal to that word + `и`
    is split into the two (`брати` → `брат и`). Whisper turbo wrote `брат ѝ` as `брати` in 3 of 4 t5 adult
    fixtures. Owner 2026-11-18; cases `glued-short-i-*`. Core version 0.3.0. **Superseded by rule 18** (its cases
    stay and pass through rule 18's exact glue).

Owner decisions 2026-11-19 (core version 0.4.0; specialist cases, then 2 challengers, then owner re-approval;
all constants untuned):

16. **Stray far match after a stop.** After the anchor pass, find the last jump: more than `STRAY_JUMP` (5) text
    words between two anchors, the start of the text counting as an anchor. When the anchors after that jump
    cover at most `STRAY_MAX_WORDS` (2) text words and not the text's last word, they are dropped and their heard
    tokens go back to the tail gap. Repeated until nothing changes. It counts anchored text words, not heard
    tokens, so a trailing engine phrase or a syllable split does not change the result. Errs toward
    `not_attempted` (harmless) over `skipped` (shames the child). Cases `stray-*`, `real-skip-ending-on-last-word`,
    `early-stop-two-fillers`. Two companions: (a) **tail join floor**: after the last anchor, joined fragments
    (2 or more) match a word only with similarity ≥ 0.5, so fillers after a stop are insertions; (b) **token
    coverage**: when two anchor choices match the same number of text words, the one covering more heard tokens
    wins (`то пла та` anchors `топлата`, not `то`).
17. **Vowel reduction.** In `judge()` only (after `equivalent`, before the 4-letter gate; anchors, repeats and
    rule 14 stay strict): `heard` is `correct` when it has the text word's length, the text word has ≥ 2 vowel
    letters (а е и о у ъ ю я), every differing position (compared letter by letter) is an о/у or а/ъ pair in
    either direction, and 1 to (vowels − 1) positions differ. ю and я count as vowels but are never a covered
    position. е/и and я/е are left out (`пие`/`пее` stays a misread). Sources: Sabev et al., Interspeech 2023
    (о/у); Andreeva et al. 2013 (а/ъ, debated). Cases `reduction-*`. `WordMark.via` = `"reduction"`.
18. **Glued words** (takes over rule 15). **Exact glue** (anchor pass): one heard token, or up to 5 joined
    fragments, of ≥ `GLUE_MIN_LEN` (3) letters anchors two consecutive text words when it splits into two parts
    each `equivalent` to its word (`милапее`, `слонае`, `вкъщи`), or is the two words with a shared consonant
    merged (`братича`). On a tie, separate anchors win; a heard word that is one text word (`затова`) is never
    split. **Near glue** (gap DP): one heard token covers two gap words when a prefix or suffix of ≥
    `GLUE_MIN_EXACT` (3) letters is `equivalent` to one word and the rest has similarity ≥ 0.5 to the other. The
    exact part is correct. The rest is `unsure` when it is one dropped or added letter away (Levenshtein 1,
    length ± 1), an explicit exception to the ≤ 4-letter rule (engine artefact; ADR 0001 note); otherwise the
    normal `judge()` applies (rule 17 included). Each word gets its own part as `heard`. At most 2 words. Cases
    `glued-*`, `separate-short-drop-stays-misread`. `WordMark.via` = `"glue"`.
19. **Tail echo is a misread** (owner 2026-11-19, fixture f10). After the last anchor, a heard token that exactly
    matches an earlier text word `r` is not a repeat of `r` (so not a free stop) when all hold: (a) `r` is not
    the word just read; (b) the previous heard token does not match `r − 1` (no phrase reread); (b') the next
    heard token does not match `r + 1` (no older phrase reread); (c) similarity to the word being placed ≥ 0.5,
    all word lengths (`да` for `на` is a misread; accepted risk: a parent's "да" after the child stops); (e) `r`
    was an exact anchor (otherwise the echo is a late self-correction; last attempt wins). The echo need not be
    the last heard token. Then the misread option wins and `judge()` decides the mark. Mid-text gaps are
    unchanged (a skip already costs 1). Core version 0.5.0. Cases `rule19-*`.
    Accepted risk (owner 2026-11-19, fixtures f10/f12/f14): turbo wrote "пее" both for a spoken пасе (f10) and a
    spoken пее (f12), so a transcript cannot tell a real misread from an engine echo, and rule 19 may mark a
    correct t1 "пасе" as misread (at worst one false "try again"). The echo did not repeat in the f14 re-take.
    t1 stays as it is.
    **(c) chain** (owner 2026-11-19, aligner step 5, core 0.6.0, fixture f12): the echo may instead be close to
    a later tail word `w`, when each of the `w − g` heard tokens just before it, all inside the tail gap, is ≥ 0.5
    to the matching text word before `w` and **strictly closer** to it than to the word before that one. So in
    `вода куза пее`, куза is коза's attempt (rule 17, correct) and пее is пасе's misread. The strict part keeps a
    token that is really an attempt at the earlier word (`пие воа пее`: воа is вода's, also 0.5 to коза) from
    carrying the chain. **An echo is not a retry** (narrow): when the echo opens the tail gap, or a chain of at
    least one sloppy attempt backs it, it gets no re-attempt option either (it made a correctly read пие misread
    "пее" in `тото пие куза пее`). Otherwise re-attempts stand (`пие ъъъ пие`, `тото пие вода пие`). Cases
    `rule19-chain-*`, `rule19-echo-is-not-a-retry`, `retry-*`.
    Accepted risks (owner 2026-11-19, D4): an echo two or more words ahead keeps the earlier word and leaves the
    rest `not_attempted` where a teacher might mark skipped + misread (`rule19-chain-echo-two-ahead-*`,
    `-three-ahead-*`); a garbled transcript can give three misreads (`rule19-chain-two-guesses-then-echo`); a
    4-letter dropped vowel is a misread (`кза`, exact rule); the 0.5-floor "да" risk reaches a word ahead only
    through the chain (`rule19-chain-short-echo-at-floor`). A stutter after an exact word (`пее пе`) is a
    re-attempt by rule 6, so the word is misread "пе" (`rule19-chain-survives-stutter`; teacher view in the known
    limits). Open (D3): guard (e) leaves пасе `not_attempted` in `rule19-guard-e-late-self-correction-*`; the
    specialist's teacher view (~60%) is a misread.

`WordMark.via` is core-only and never written to the log (no schema change); the engine eval can re-run `align`
and count how many marks rules 17 and 18 decided.

## Known limits (strict expected failures)

A case with `"known_limit": true` runs as `xfail(strict=True)`: it documents a limit the owner chose to fix later,
and an accidental fix turns it red (XPASS) so the flag is removed on purpose.

- `reduction-hides-*` (rule 17): real twins that differ only in a reduced vowel (`дома`/`дума`, `кола`/`кула`,
  `ръка`/`рака`, `мъка`/`мака`) are marked correct. Fixable later with a short twin list.
- `glued-three-words` (rule 18): a heard token gluing 3 words (`мамаибаба`) is not split.
- Aligner step 5 (owner 2026-11-19, core 0.6.0), each with the step that fixes it; expected = teacher marks
  (specialist-confirmed where the note gives a %):
  - **Step 6 (H2, gate before ADR 0003 and any child session or engine eval on child audio):**
    `anchor-tie-steals-echo-mid-text` (false `skipped`), `anchor-tie-steals-echo-tail` (lost credit / missed
    misread).
  - **Step 7 (joined forms, H1):** `tail-join-floor-swallows-short-word`, `messy-tail-stutter-and-split-echo`
    (L1: a new `skipped` on a very messy tail), `messy-tail-glued-echo-misread` (L2).
  - **Step 8 (an echo of an older word becomes a re-attempt):** `older-echo-after-last-word-is-not-a-retry`
    (K1), `older-echo-after-word-is-not-a-retry` (K2), `rule19-chain-broken-by-filler` (K3),
    `rule19-echo-of-word-just-read-after-sloppy-word` (K4), `older-echo-after-filler-is-not-a-retry` (K6),
    `older-echo-mid-text-is-not-a-retry` (K7, mid-text, so step 8 is not closed on the tail alone),
    `messy-tail-late-reduced-word-takes-credit` (L3, lost credit).
  - **Step 9 (narrow rule 6):** `stutter-prefix-keeps-exact-word`: a strict prefix right after a word read
    exactly is a stutter, and the word stays correct.

Known limits, accepted 2026-11-19 (no case fails on them):

- Rule 16: a real skipped line followed by reading at most 2 words and stopping reads as an early stop
  (`not_attempted`, not `skipped`). A deliberate trade (`stray-two-adjacent-text-words-far`).
- Rule 17: stress is not checked, so a changed stressed vowel can be accepted (`мама`/`мъма` is correct, because
  without stress it cannot be told apart from `мама`/`мамъ`).

Known limits, accepted: unsure hides some real ending misreads (`лодка` → `лодки` = 0.80); `стоят` → `стоя` is
treated as an article pair.

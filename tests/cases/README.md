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

Known limits, accepted: unsure hides some real ending misreads (`лодка` → `лодки` = 0.80); `стоят` → `стоя` is
treated as an article pair.

# Audio fixtures

Every audio file under `tests/fixtures/` has a line here: who recorded it, adult or synthetic
(`tests/unit/test_child_data_ignores.py` enforces this). No child's voice, ever.

## Adult recordings, local only (`audio-local/`)

The owner's own voice. Gitignored and excluded from the M2 sync (step 2 plan S2): only the sidecars in
`sidecars/` are committed. Tests that need a WAV fail loudly when it is missing.

Record each clip on M1 (quiet room, no child audible), following the `instructions` in its sidecar:

```bash
bash scripts/record-fixture.sh <id> [seconds]   # shows the text in a window; closes itself when saved
```

| File | Text | Kind | Recorded by | Speaker |
|---|---|---|---|---|
| `audio-local/f01-t1-clean.wav` | t1-mila-pee | clean | owner | adult |
| `audio-local/f02-t1-syllables.wav` | t1-mila-pee | syllable by syllable | owner | adult |
| `audio-local/f03-t1-misreads-skip.wav` | t1-mila-pee | 2 misreads + 1 skip | owner | adult |
| `audio-local/f04-t1-repeats-selfcorr.wav` | t1-mila-pee | repeats + self-correction | owner | adult |
| `audio-local/f05-t5-clean.wav` | t5-patitsite-v-parka | clean (adult pace) | owner | adult |
| `audio-local/f06-t5-syllables.wav` | t5-patitsite-v-parka | syllable by syllable, stops after word 17 | owner | adult |
| `audio-local/f07-t5-misreads-skip.wav` | t5-patitsite-v-parka | 2 misreads + 1 skip, stops after word 24 | owner | adult |
| `audio-local/f08-t5-repeats-selfcorr.wav` | t5-patitsite-v-parka | repeats + self-correction, stops after word 17 | owner | adult |
| `audio-local/f09-t1-browser-repro.wav` | t1-mila-pee | 2 misreads (бама, вие): repeat of the first laptop-browser check | owner | adult |
| `audio-local/f10-t1-reduction.wav` | t1-mila-pee | natural vowel reduction (rule 17), all correct | owner | adult |
| `audio-local/f11-t5-stop-silence.wav` | t5-patitsite-v-parka | stops after word 14, then ~5 s silence (rule 16 vs trailing hallucinations) | owner | adult |

The full set of 30 clips comes before any engine verdict (step 2 plan S6).

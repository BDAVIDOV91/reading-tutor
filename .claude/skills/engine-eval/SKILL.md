---
name: engine-eval
description: How to produce and report an engine comparison for the reading tutor without children's data entering the session. Use when asked which engine is better, how accurate an engine is, whether results are good enough, or when writing the testing checklist or a go/no-go summary.
---

# Engine evaluation

The prototype's answer ("can speech recognition follow a child and detect mistakes?") comes from this
procedure. Claude sees aggregate numbers only.

## Rules

- Never read `recordings/` or `data/`, the attempts table, or the CSV export: they hold children's transcripts.
- The owner runs the aggregate report in their own terminal (`! <command>` in the prompt) and its output is the
  only evaluation input. If output contains transcript text, stop and fix the report so it does not.
- Every number is reported with its sample and population. Adult-fixture numbers are never called child accuracy.

## Steps

1. **Check the report command exists.** It prints, per engine and per text level: attempts, words, words the
   parent marked wrong, and the four cells of *parent wrong / app wrong*. Counts only, no text. If it does not
   exist yet, building it (test-first) is the task; the metric definitions come from the `engine-evaluator` agent.
2. **Ask the owner to run it** and paste the output.
3. **Compute per engine:** mistake recall, mistake precision, false flags per 100 correctly read words, agreement
   with the parent, median transcription time. Rates on fewer than about 30 real mistakes are given as counts.
4. **Hand the table to `engine-evaluator`** for interpretation when the result will drive a decision (dropping
   an engine, go/no-go).
5. **Report** in this shape:

   ```
   Sample: N attempts, W words, M real mistakes; speakers: <child / adult fixture>; levels: <...>; device: <...>
   | Engine | Audio goes to | Recall | Precision | False flags /100 | Agreement | Median time |
   Supports: <what the numbers allow us to say>
   Does not support: <what they do not>
   Next recordings: <which would reduce uncertainty most>
   ```

6. **Save** a dated summary to `docs/research/YYYY-MM-DD_engine-eval.md` (aggregates only) once the owner
   approves it.

## Go / no-go

Thresholds are the owner's decision, recorded once in `docs/adr/`. Until then, present numbers without a verdict.

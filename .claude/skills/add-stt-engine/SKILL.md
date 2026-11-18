---
name: add-stt-engine
description: Checklist for adding or changing a speech-to-text engine in the reading tutor (local model, browser engine or cloud API). Use when a plan or task adds an engine, switches a model, or changes where audio is sent.
---

# Add an STT engine

An engine is anything that turns a recording into Bulgarian text. Adding one can send a child's voice off the
laptop, so the order below is fixed: decide and record first, code second.

## Steps

1. **Classify the engine.** Write down: name and model, `local` or `cloud:<provider>:<region>`, cost and free
   quota with the source URL and the date checked, licence of the model or terms of the API.
   *Stop* if it costs money at the expected usage: the budget is zero, ask the owner.
2. **Cloud engine only: ADR before code.** Ask the owner through `AskUserQuestion` whether audio may go to this
   provider. On yes, write `docs/adr/NNNN-<engine>.md`: region chosen, each retention / logging / training
   setting and how it is switched off, with the provider page cited for each. No ADR, no call with a real
   recording.
3. **RED test.** Add a test for the new engine against the shared engine interface with the network or model
   mocked: returns a transcript for a fixture, reports its `audio destination` value, surfaces a timeout and a
   failure as a typed error without losing the recording.
4. **Implement behind the interface.** No engine-specific code in alignment, scoring or UI. The key (if any) is
   read from `.env` on the server; add the variable name, without a value, to `.env.example`.
5. **Do not feed the expected text to the engine** (prompt, phrase hints, custom vocabulary) unless a test with
   deliberately misread fixtures shows the misreadings still come through. Biasing toward the target text can
   hide the mistakes the product exists to detect.
6. **Fixture run.** Run the engine on the adult-recorded fixtures (`reading-fixtures` skill) and record latency
   and the transcript for each. This is "test-verified" on adults only.
7. **Register it.** Engine appears in the engine setting and in "run through all engines"; the UI shows its
   audio destination next to its name.
8. **Review and report.** Run the `privacy-reviewer` agent on the diff. Checkpoint as in `CLAUDE.md`, stating
   that accuracy on children is unmeasured until the owner's device test.

## Done when

The engine passes its mocked tests and the fixture run, the ADR exists if it is a cloud engine, `privacy-reviewer`
returns `pass`, and the full suite is green.

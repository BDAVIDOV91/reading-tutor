---
status: accepted
date: 2026-11-18
---

# The prototype runs in the laptop browser first, not on the phone

Brief scope item 1 puts the prototype on a phone. The owner decided (2026-11-18) that the first loops run in the
laptop's own browser instead: `localhost` is a secure context, so the microphone works with no cable, no
certificate and nothing exposed on the home network. The cost is that a laptop microphone is not the product's
microphone, so laptop results do not prove phone accuracy.

## Rules that follow

- Every attempt logs its input device (`input_device_class`, `mime_type`, `track_settings`; ADR 0001).
- **Gate:** a laptop "yes" moves on to the phone microphone, and is not a product yes until the phone repeat
  passes the same thresholds. A laptop "no" is not final until it is repeated with a phone microphone, with the
  same texts, thresholds and minimum sample.
- **Verification words:** "laptop-verified" (seen working in the laptop browser with the laptop microphone) is
  never reported as "device-verified" (seen working on the phone with a real microphone). A headless browser run
  with a fake microphone is "test-verified" only.
- mkcert (a local certificate for the phone over the home network) is deferred until the phone step. No tunnel
  and no public URL at any step.

## Considered options

- **Phone from day one over `adb reverse`**: works on Android only, with the phone cabled; adds setup before the
  core loop has any numbers.
- **Phone over mkcert**: whether Chrome Android trusts a user-installed root CA is an unverified device check.

## Consequences

- Hidden mistakes (low recall, few false flags) come mainly from the engine, so a phone microphone is unlikely to
  fix low recall; it is more likely to change the false-flag rate. If possible, one session is recorded on both
  at once to separate the microphone from the child.

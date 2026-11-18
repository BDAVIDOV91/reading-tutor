# CLAUDE.md

Bulgarian reading tutor prototype. A child (age 6 to 8) reads a Bulgarian text aloud; the app transcribes, aligns
and scores it. The prototype answers one question: can speech recognition follow such a child and detect mistakes?

**Brief:** `docs/PROTOTYPE_BRIEF.md`. Build **Part 2 only**. Part 1 is context, never a task.
**Budget:** zero. No paid API, plan or credit without the owner's explicit yes.
**Skills and agents:** who may invoke what is in `docs/SKILLS.md`.

## Workflow

1. **Plan mode** for anything beyond a one-line change.
2. **`grilling`** (or `grill-with-docs` when terms or one-way decisions come up) until the design tree is settled.
3. **Challenge:** after plan approval a hook asks "Challenge or proceed?". On Challenge, spawn 2 `challenger`
   agents in parallel with the plan path, then merge their findings into the plan.
4. **Build test-first** (superpowers `test-driven-development`). Keep core logic (normalise, align, score) free of
   UI and browser code so the later native app can reuse it.
5. **Before the checkpoint**, run the `privacy-reviewer` agent when the diff touches audio, storage, STT clients,
   logging or the server.

Repo skills: `add-stt-engine`, `engine-eval`, `reading-fixtures`. Repo agents besides `challenger`:
`bulgarian-reading-specialist` (texts, normalisation, test cases), `engine-evaluator` (comparison method, numbers),
and three researchers (`stt-researcher`, `privacy-law-researcher`, `browser-audio-researcher`).
Never delegate to `general-purpose`: if no named agent fits, create one with a name and purpose first
(`docs/SKILLS.md`).

**Per fix:** write a test that fails on the old code (RED), fix, see it pass (GREEN), run the full suite. The test
stays in the suite forever. No fix ships without its own regression test.

**Verification words:** "test-verified" means an automated test passed. "device-verified" means it was seen
working on the phone with a real microphone. Never merge the two, and never claim the second from the first.

## Decisions

Anything that needs the owner's answer, approval or hands goes through `AskUserQuestion` at the moment it is
found, not in the next summary. Recommended option first, labelled "(Recommended)", and its description ends with
`~NN%` certainty. Keep working on whatever does not depend on the answer. A hook logs each answer to
`~/.claude/projects/-home-technojihad-reading-tutor/decision-log.jsonl`.

One-way decisions (engine choice that sends audio off the machine, storage format, anything touching consent) get
an ADR in `docs/adr/` (format: `.claude/skills/domain-modeling/ADR-FORMAT.md`). Research goes to
`docs/research/YYYY-MM-DD_slug.md` with sources.

## Completion checkpoint

On task completion, STOP and report:
- **What changed** (what + files)
- **Evidence** (before → after: RED→GREEN test output, or saved proof)
- **Door / Blast radius** (one-way or two-way; what it can break)

After the owner approves: update docs, commit, suggest the next task, then stop.

## Git

- No `git stash`, no `git push` (the owner pushes), no `git add -A` / `.` / `-u`, no `git add -f`.
- Commit with `git commit --only -m "..." -- <paths>` (new files: `git add <paths>` first).
- `.claude/hooks/block-dangerous-git.sh` enforces this, for sub-agents too. When a call is BLOCKED, do not retry,
  rephrase or edit the hook; the owner runs it in their own terminal if they want it.
- Changing a hook: add a case to its `test-*.sh` first. `.githooks/pre-commit` runs every hook test when a hook or
  `.claude/settings.json` is staged. Fresh clone: `git config core.hooksPath .githooks`.

## Child data (non-negotiable)

- Recordings and transcripts of real children never enter a Claude session, the repo, a log, a test or a prompt.
  Do not read, play, transcribe or list the contents of `recordings/` or `data/`.
- Tests and debugging use invented text or adult-recorded fixtures under `tests/fixtures/`.
- Recordings stay on the owner's device or laptop. No public URL, no tunnel, no third-party upload unless an ADR
  and the owner's explicit yes cover that engine.
- API keys live only in `.env` (gitignored): never in frontend code, the repo or a command line.
- Detail for audio, storage and STT client code: `.claude/rules/child-data.md`.

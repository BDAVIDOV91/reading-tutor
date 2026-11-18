# Provenance: Pocock skills

Vendored from https://github.com/mattpocock/skills ("Skills for Real Engineers", MIT license), pinned at commit
`b0618bc4` (`b0618bc436ad893b3c5e84e55fba86586d34a404`). Copied on 2026-11-18 from the owner's
`pdf_data_extractor_v2` repo, which vendored them at that pin; that repo's local `KNA:` blocks were removed, so
each file equals upstream at the pin except for the differences in the Notes column.

| Local skill | Upstream path | Notes |
|---|---|---|
| `grilling` | `skills/productivity/grilling` | Interview primitive. Upstream text only. |
| `grill-with-docs` | `skills/engineering/grill-with-docs` | Calls `grilling` + `domain-modeling`. Upstream's `disable-model-invocation: true` frontmatter line is removed on purpose, so it can run in plan mode (`docs/SKILLS.md`). Keep it removed on a re-pin. |
| `domain-modeling` | `skills/engineering/domain-modeling` | + `GLOSSARY-FORMAT.md`, `ADR-FORMAT.md`. Upstream text only. |
| `writing-for-agents` | `skills/productivity/writing-for-agents` | + `SKILL-MECHANICS.md`. Reference for editing CLAUDE.md, skills and agent docs. |
| `wait-what` | `skills/productivity/wait-what` | OWNER-typed. Upstream text only. |
| `retro` | `skills/engineering/retro` | OWNER-typed (`disable-model-invocation: true` kept). Upstream text only. |

Not a skill, but from the same collection: `.claude/hooks/block-dangerous-git.sh` is adapted from
`skills/misc/git-guardrails-claude-code/scripts/block-dangerous-git.sh` (patterns customised: adds `git stash`,
`gh pr create`, `git add -f` and blanket `git add`; regression test `.claude/hooks/test-block-dangerous-git.sh`).

Do not install the upstream plugin (`claude plugins install mattpocock-skills`): it loads every upstream skill
description into each turn. Vendor single skills instead, and add a row here and in `docs/SKILLS.md`.

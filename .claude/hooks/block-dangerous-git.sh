#!/usr/bin/env bash
# PreToolUse(Bash) hook: HARD-BLOCK destructive git before it runs.
#
# Enforces two standing CLAUDE.md rules mechanically instead of by prose:
#   - NEVER push (owner pushes manually; covers `gh pr create`)
#   - NEVER `git stash` (shared working tree + synced .git; bit a sub-agent 2026-09-07)
# plus the usual irreversible ones (reset --hard, clean -f, branch -D, checkout/restore .).
#
# Hooks fire for sub-agent Bash calls too, so this covers "applies to sub-agents".
# If a blocked command is genuinely needed, the OWNER runs it in their own terminal.
# The agent must never edit this file or the pattern list to get past it.
#
# Adapted from mattpocock/skills `git-guardrails-claude-code` (MIT, pinned 3cca18b).
# Regression test: .claude/hooks/test-block-dangerous-git.sh
# Blanket staging (git add -A/./-u) is blocked since 2026-10-08: peers share the working tree.
# 2026-11-08 (M2 milestone, Q10): `purge_client_corpus.sh --execute` (any path form) is blocked too; owner-only.
#
# Exit 2 + stderr = Claude Code blocks the call and shows the message to the model.

input="$(cat)"
if command -v jq >/dev/null 2>&1; then
  cmd="$(printf '%s' "$input" | jq -r '.tool_input.command // ""' 2>/dev/null)"
else
  cmd="$(printf '%s' "$input" | python3 -c "import sys,json;
try: print(json.load(sys.stdin).get('tool_input',{}).get('command',''))
except Exception: print('')" 2>/dev/null)"
fi
[ -z "$cmd" ] && exit 0

# Two parallel arrays (a separator char inside an ERE is a trap: `|` truncated the
# patterns once). Patterns anchor on the git/gh verb, skipping global options
# (`-c x`, `-C <dir>`, `--git-dir=x`), so `git commit -m "fix push"` does not trip.
# Quoted text is NOT stripped first: `bash -c "git push"` must still be caught
# (quotes escaping an anchor was the 2026-08-23 pin-list bug). Over-blocking an
# echo/grep that merely mentions the words is the cheap side to err on.
G='\bgit([[:space:]]+(-[cC][[:space:]]+[^[:space:]]+|-[^[:space:]]+))*[[:space:]]+'
patterns=(
  "${G}push\b"
  '\bgh[[:space:]]+pr[[:space:]]+create\b'
  "${G}stash\b"
  "${G}reset\b[^;&|]*--hard"
  "${G}clean\b[^;&|]*[[:space:]]-[[:alnum:]]*f"
  "${G}branch\b[^;&|]*[[:space:]](-[[:alnum:]]*D|--delete[[:space:]]+--force|--force[[:space:]]+--delete)\b"
  "${G}(checkout|restore)[[:space:]]+(--[[:space:]]+)?\.([[:space:]]|$|;|&|\|)"
  "${G}add\b[^;&|]*[[:space:]](-[[:alnum:]]*f[[:alnum:]]*|--force)([[:space:]]|$)"
  "${G}add\b[^;&|]*[[:space:]](-[[:alnum:]]*[Au][[:alnum:]]*|--all|--update|\./?)([[:space:]]|$|;|&|\|)"
  'purge_client_corpus\.sh[^;&|]*--execute'
)
rules=(
  'NEVER PUSH (owner pushes manually)'
  'NEVER PUSH (gh pr create publishes the branch)'
  'NEVER git stash (shared working tree, synced .git)'
  'git reset --hard is irreversible'
  'git clean -f deletes untracked files'
  'git branch -D discards unmerged work'
  'git checkout/restore . wipes every uncommitted edit'
  'NEVER git add -f (gitignored paths are where .env files and client PII sat, TG-129/134; tell the owner instead)'
  'NEVER blanket-stage (git add -A/./-u): sessions share one working tree, so it stages a peer'"'"'s edits. Name the paths and commit with git commit --only -- <paths>'
  'NEVER run purge_client_corpus.sh --execute (it deletes the client corpus; only the OWNER runs it, in their own terminal, after the store purge)'
)

for i in "${!patterns[@]}"; do
  if printf '%s' "$cmd" | grep -qE "${patterns[$i]}"; then
    printf 'BLOCKED by .claude/hooks/block-dangerous-git.sh — rule: %s.\nCommand: %s\nThis is a standing CLAUDE.md rule enforced by a hook, not a permission prompt. Do not retry, rephrase, or edit the hook. If the owner truly wants this, they run it themselves.\n' "${rules[$i]}" "$cmd" >&2
    exit 2
  fi
done
exit 0

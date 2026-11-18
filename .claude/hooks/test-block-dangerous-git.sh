#!/usr/bin/env bash
# Regression test for .claude/hooks/block-dangerous-git.sh (PreToolUse hook).
#
# The hook is the mechanical form of two CLAUDE.md rules (NEVER push, NEVER stash).
# A silent miss lets a sub-agent stash the other worker's edits or push the branch;
# a false positive blocks ordinary git and gets the hook disabled. Both matter.
#
# Feeds the hook the same JSON Claude Code sends on stdin. Never runs git.

set -uo pipefail
H="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/block-dangerous-git.sh"
pass=0; fail=0

check() { # check <expect: block|allow> <command>
  local expect="$1" cmd="$2" rc got
  printf '{"tool_name":"Bash","tool_input":{"command":%s}}' "$(printf '%s' "$cmd" | python3 -c 'import json,sys;print(json.dumps(sys.stdin.read()))')" \
    | bash "$H" >/dev/null 2>&1; rc=$?
  case "$rc" in 2) got=block ;; 0) got=allow ;; *) got="rc=$rc" ;; esac
  if [ "$got" = "$expect" ]; then
    printf '  ok    %-5s  %s\n' "$expect" "$cmd"; pass=$((pass+1))
  else
    printf '  FAIL  want=%s got=%s  %s\n' "$expect" "$got" "$cmd"; fail=$((fail+1))
  fi
}

echo "must BLOCK:"
check block 'git push'
check block 'git push origin development'
check block 'git push --force-with-lease'
check block 'cd nc-backend && git push -u origin HEAD'
check block 'git -C /home/technojihad/pdf_data_extractor_v2 push'
check block 'gh pr create --fill'
check block 'git stash'
check block 'git stash pop'
check block 'git stash list'
check block 'git stash push -m wip -- nc-frontend'
check block 'yarn build; git stash; yarn test'
check block 'git reset --hard HEAD~1'
check block 'git reset --hard origin/main'
check block 'git clean -fd'
check block 'git clean -xdf'
check block 'git branch -D feature/x'
check block 'git branch --delete --force feature/x'
check block 'git checkout .'
check block 'git checkout -- .'
check block 'git restore .'
check block 'git restore . && yarn test'
check block 'bash -c "git push origin main"'
check block 'git --git-dir=.git push'
check block 'git -c user.name=x push'
# git add -f/--force (2026-09-15, CF1-6): gitignored paths are where TG-129/134 PII sat
check block 'git add -f nc-backend/.env.production'
check block 'git add -Af'
check block 'git add --force .claude/rules/x.md'
check block 'git -C /home/technojihad/pdf_data_extractor_v2 add -f x'
check block 'bash -c "git add -f x"'
# deliberate over-block: a path literally named -f after --
check block 'git add x -- -f'
# deliberate over-block: quotes must not escape the guard (2026-08-23 pin-list lesson)
check block 'echo "git push is forbidden" > notes.txt'
check block 'grep -rn "git stash" CLAUDE.md'
# allnighter night tree (plan Phase A step 3, 2026-10-04): the blocks must also fire with -C on the
# night worktree, which shares .git with the main tree. No hook change; guards a regression.
check block 'git -C /home/technojihad/pdfx-night push'
check block 'git -C /home/technojihad/pdfx-night push origin allnighter/2026-10-04'
check block 'git -C /home/technojihad/pdfx-night stash'
check block 'git -C /home/technojihad/pdfx-night reset --hard HEAD'
check block 'git -C /home/technojihad/pdfx-night clean -fd'
check block 'git -C /home/technojihad/pdfx-night branch -D allnighter/2026-10-04'
check block 'HUSKY=0 git -C /home/technojihad/pdfx-night add -f nc-backend/.env'
# blanket staging (2026-10-08 retro): three sessions share one working tree, so a blanket add stages
# the peers' uncommitted edits into this session's commit. Stage named paths; commit with --only.
check block 'git add -A'
check block 'git add -A nc-backend/'
check block 'git add --all'
check block 'git add .'
check block 'git add ./'
check block 'git add -- .'
check block 'git add . && git commit -F msg.txt'
check block 'git add -u'
check block 'git add --update'
check block 'cd nc-frontend && git add -u src/'
check block 'git -C /home/technojihad/pdf_data_extractor_v2 add -A'

# 2026-11-08 (M2 milestone, Q10): the client-corpus deletion script is owner-only, never a Claude call
check block './ops/pii-redaction/purge_client_corpus.sh --execute'
check block 'bash ops/pii-redaction/purge_client_corpus.sh --execute'
check block 'bash /home/technojihad/pdf_data_extractor_v2/ops/pii-redaction/purge_client_corpus.sh --execute'
check block 'cd ops/pii-redaction && ./purge_client_corpus.sh --execute'
check block 'cd ops/pii-redaction && bash purge_client_corpus.sh --execute'
check block 'sh -c "bash ops/pii-redaction/purge_client_corpus.sh --execute"'
check block 'PURGE_TEST_MODE=1 bash ops/pii-redaction/purge_client_corpus.sh --execute'
check block 'bash ops/pii-redaction/purge_client_corpus.sh --inventory && bash ops/pii-redaction/purge_client_corpus.sh --execute'

echo "must ALLOW:"
check allow 'git status'
check allow 'git commit -m "fix: push logic in queue worker"'
check allow 'git log --oneline --grep stash'
check allow 'git show HEAD:nc-backend/src/main.ts'
check allow 'git reset HEAD~1'
check allow 'git reset --soft HEAD~1'
check allow 'git restore --staged nc-frontend/src/routes/privacy.tsx'
check allow 'git checkout development'
check allow 'git checkout -b feat/x'
check allow 'git branch -d merged-branch'
check allow 'git clean -n'
check allow 'git diff --stat'
check allow 'git add -- file-f.ts'
check allow 'git add -p'
check allow 'git add --refresh'
check allow 'git add a-f.ts docs/x.md'
check allow 'git commit -F msg.txt'
check allow 'git add x && git commit -F msg.txt'
check allow 'git add -N ops/retro/new-file.sh'
check allow 'git add --intent-to-add ops/retro/new-file.sh'
check allow 'git add ./ops/retro/session-gate.sh'
check allow 'git add .claude/hooks/x.sh'
check allow 'git add docs/u.md src/A.ts'
check allow 'git commit --only -m x -- .claude/hooks/x.sh'
check allow 'bash .claude/hooks/test-doc-freshness.sh'
check allow 'gh pr list'
check allow 'gh pr view 12'
check allow 'ls'
check allow 'bash ops/pii-redaction/purge_client_corpus.sh --inventory'
check allow 'bash ops/pii-redaction/purge_client_corpus.sh'
check allow 'bash ops/pii-redaction/test_purge_client_corpus.sh'
check allow ''

echo; echo "pass=$pass fail=$fail"
[ "$fail" -eq 0 ]

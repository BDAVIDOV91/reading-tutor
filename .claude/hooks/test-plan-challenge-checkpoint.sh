#!/usr/bin/env bash
# Regression test for plan-challenge-checkpoint.sh (PostToolUse on ExitPlanMode).
# Run: bash .claude/hooks/test-plan-challenge-checkpoint.sh
#
# 2026-09-15 (audit #11, RED->GREEN): the checkpoint told the model to hand challengers "the newest
# ~/.claude/plans/*-agent-*.md". That glob matched no plan file, and "newest" in a directory shared by
# every session can be another session's plan. The same dead fallback sat in .claude/agents/challenger.md.
# The text also named the renamed "Task tool" and asked Challenge/Proceed with no (Recommended) option.
# Offline, no git.
set -uo pipefail
H="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$H/../.." && pwd)"
HOOK="$H/plan-challenge-checkpoint.sh"
pass=0; fail=0
ok()  { printf '  ok    %s\n' "$1"; pass=$((pass+1)); }
bad() { printf '  FAIL  %s\n' "$1"; fail=$((fail+1)); }
# has <text>: fixed-string match on $msg via a here-string (never a pipe under pipefail).
has() { grep -qF -- "$1" <<< "$msg"; }

payload() { # payload <tool_name> <tool_input.planFilePath|""> <tool_response.filePath|"">
  python3 - "$1" "$2" "$3" <<'PY'
import json, sys
tool, in_path, resp_path = sys.argv[1], sys.argv[2], sys.argv[3]
ti = {"plan": "# plan"}
tr = {"plan": "# plan", "isAgent": False}
if in_path:
    ti["planFilePath"] = in_path
if resp_path:
    tr["filePath"] = resp_path
print(json.dumps({"session_id": "s-test", "hook_event_name": "PostToolUse", "tool_name": tool,
                  "tool_input": ti, "tool_response": tr}))
PY
}

run() { # run <stdin text> -> sets out, rc, event, msg
  out=$(printf '%s' "$1" | bash "$HOOK" 2>/dev/null); rc=$?
  event=$(python3 -c 'import json,sys; print(json.loads(sys.stdin.read())["hookSpecificOutput"]["hookEventName"])' <<< "$out" 2>/dev/null)
  msg=$(python3 -c 'import json,sys; print(json.loads(sys.stdin.read())["hookSpecificOutput"]["additionalContext"])' <<< "$out" 2>/dev/null)
}

echo "checkpoint message:"
run "$(payload ExitPlanMode "" /x/plans/foo-bar.md)"
[ "$rc" -eq 0 ] && ok "exit 0 on ExitPlanMode" || bad "exit $rc on ExitPlanMode"
[ "$event" = "PostToolUse" ] && ok "stdout is one JSON object for PostToolUse" || bad "unparseable or wrong event: $out"
for s in 'Challenge' 'Proceed' 'TWO' 'IN PARALLEL' 'challenger' '## Challenger Findings' 'never overwrite'; do
  has "$s" && ok "contract kept: $s" || bad "contract lost: $s"
done
has '/x/plans/foo-bar.md' && ok "names the plan path from tool_response.filePath" || bad "tool_response.filePath not in the message"
has 'Agent tool' && ok "names the Agent tool" || bad "does not name the Agent tool"
has 'Task tool' && bad "still names the renamed Task tool" || ok "no Task tool"
has '(Recommended)' && ok "checkpoint question needs a (Recommended) option" || bad "no (Recommended) in the checkpoint question"

run "$(payload ExitPlanMode /y/plans/in-put.md "")"
has '/y/plans/in-put.md' && ok "falls back to tool_input.planFilePath" || bad "tool_input.planFilePath not in the message"

run "$(payload ExitPlanMode "" "")"
has 'Your plan has been saved to:' && ok "no path -> points at the ExitPlanMode result line" || bad "no-path fallback missing"
has -agent- && bad "no-path message still names the dead *-agent-* glob" || ok "no *-agent-* glob"
has newest && bad "no-path message still picks the newest plan" || ok "never picks by mtime"

echo "already challenged (2026-10-08 retro: re-exiting plan mode re-asked a challenged plan):"
P=$(mktemp -d); trap 'rm -rf "$P"' EXIT
printf '# plan\n\nsteps\n\n## Challenger Findings (A: REVISE, B: APPROVE)\n\n- a finding\n' > "$P/both.md"
printf '# plan\n\n## Challenger Findings (2026-10-02, A + B, both REVISE, high confidence)\n\n- x\n' > "$P/both-word.md"
printf '# plan\n\n## Challenger Findings\n\nChallenger A: REVISE\nChallenger B: APPROVE\n\n## Next\n' > "$P/body.md"
printf '# plan\n\n## Challenger Findings\n\nChallenger A: REVISE\n(B still running)\n' > "$P/one.md"
printf '# plan\n\nBoth challengers said REVISE and APPROVE, in prose only.\n' > "$P/prose.md"
for f in both both-word body; do
  run "$(payload ExitPlanMode "" "$P/$f.md")"
  if [ "$rc" -eq 0 ] && has 'already challenged' && ! has 'Challenge the plan or proceed'; then ok "$f: skips the question"
  else bad "$f: still asks (rc=$rc): ${msg:0:120}"; fi
done
for f in one prose missing; do
  run "$(payload ExitPlanMode "" "$P/$f.md")"
  has 'Challenge the plan or proceed' && ok "$f: still asks" || bad "$f: skipped wrongly: ${msg:0:120}"
done
run "$(payload ExitPlanMode "" "")"
has 'Challenge the plan or proceed' && ok "no path: still asks" || bad "no path skipped"
run "$(payload ExitPlanMode "" /x/plans/foo-bar.md)"
has '(A: <VERDICT>, B: <VERDICT>)' && ok "asks for the verdict-bearing heading" || bad "heading format not requested"

echo "task list (2026-11-19: after approval, build the native task list from the plan's Steps):"
run "$(payload ExitPlanMode "" /x/plans/foo-bar.md)"
has 'native task list' && has 'TaskCreate' && ok "ask branch: names the native task list (TaskCreate)" || bad "ask branch: no task-list reminder"
run "$(payload ExitPlanMode "" "$P/both.md")"
has 'native task list' && has 'TaskCreate' && ok "already-challenged branch: names the native task list" || bad "already-challenged branch: no task-list reminder"
printf '# plan\n\n## Decisions 2026-11-19 (cases)\n\n### Challenger findings (decisions 2026-11-19): A revise, B revise\n\n- x\n\n## Steps\n' > "$P/sub.md"
run "$(payload ExitPlanMode "" "$P/sub.md")"
has 'Challenge the plan or proceed' && ok "mid-session '### Challenger findings' subsection still asks" || bad "subsection skipped the plan question"

echo "quiet on everything else:"
for p in "$(payload Bash "" /x/p.md)" "$(payload AskUserQuestion "" "")" 'not json{' ''; do
  run "$p"
  [ "$rc" -eq 0 ] && [ -z "$out" ] && ok "quiet, exit 0: ${p:0:40}" || bad "not quiet (rc=$rc): ${p:0:40}"
done

echo "real repo:"
[ -x "$HOOK" ] && ok "hook is executable (settings.json runs it by path)" || bad "hook lost +x"
dead=""
for f in "$ROOT"/.claude/agents/challenger.md "$H"/*.sh; do
  [ "$f" -ef "${BASH_SOURCE[0]}" ] && continue
  grep -qF -- '-agent-*' "$f" && dead="$dead ${f#"$ROOT"/}"
done
[ -z "$dead" ] && ok "no dead *-agent-* plan glob in hooks or challenger.md" || bad "dead *-agent-* glob in:$dead"

echo; echo "pass=$pass fail=$fail"
[ "$fail" -eq 0 ]

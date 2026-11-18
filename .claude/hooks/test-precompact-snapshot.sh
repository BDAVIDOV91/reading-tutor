#!/usr/bin/env bash
# Regression test for .claude/hooks/precompact-snapshot.sh (PreCompact hook, MENTOR-REST 2026-09-18).
#
# Before a compaction the hook writes a resume snapshot (HEAD, branch, status, plan, host, session id)
# under ~/.claude/projects/<slug>/last-compact-<session_id>.md, so the post-compaction session resumes
# from evidence instead of from the summary alone. Two things must never happen: a non-zero exit
# (exit 2 BLOCKS the compaction) and a write outside the existing project dir (the slug rule
# hyphenates every non-alphanumeric char: /home/x/pdf_data.v2 -> -home-x-pdf-data-v2; a wrong slug
# would silently create a bogus sibling dir that the reader then also uses).
#
# Builds throwaway git repos; never touches the real index, ~/.claude/plans or ~/.claude/projects.

set -uo pipefail
unset GIT_DIR GIT_INDEX_FILE GIT_WORK_TREE GIT_PREFIX GIT_OBJECT_DIRECTORY GIT_ALTERNATE_OBJECT_DIRECTORIES
HOOKS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
H="$HOOKS/precompact-snapshot.sh"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
pass=0; fail=0
ok()  { printf '  ok    %s\n' "$1"; pass=$((pass+1)); }
bad() { printf '  FAIL  %s\n' "$1"; fail=$((fail+1)); }

if [ ! -f "$H" ]; then bad "hook not found: $H"; echo; echo "pass=$pass fail=$fail"; exit 1; fi

repo() { # repo <dir>: git repo with one commit
  mkdir -p "$1"; git -C "$1" init -q; git -C "$1" config user.email t@example.invalid; git -C "$1" config user.name t
  printf 'x\n' > "$1/a.ts"; git -C "$1" add a.ts; git -C "$1" commit -q -m "base commit"
}
OUT="$T/out"; PLANS="$T/plans"; mkdir -p "$OUT" "$PLANS"
rc=0
run() { # run <json> [VAR=value ...] -> rc, out; hook env: PRECOMPACT_OUT_DIR, PRECOMPACT_PLANS_DIR, CLAUDE_PROJECT_DIR
  local json="$1"; shift
  out="$(printf '%s' "$json" | env PRECOMPACT_OUT_DIR="$OUT" PRECOMPACT_PLANS_DIR="$PLANS" "$@" bash "$H" 2>/dev/null)"; rc=$?
}
sid() { printf '{"session_id":"%s","trigger":"manual","transcript_path":"%s","cwd":"%s"}' "$1" "${2:-/nonexistent.jsonl}" "${3:-/}"; }
f() { printf '%s/last-compact-%s.md' "$OUT" "$1"; }
has() { grep -qF -- "$2" "$1"; }   # has <file> <needle>
line() { grep -n -m1 -F -- "$2" "$1" | cut -d: -f1; }

echo "(a) header first, in order:"
R="$T/a"; repo "$R"; printf 'y\n' >> "$R/a.ts"; printf 'n\n' > "$R/new.spec.ts"
run "$(sid s-a "$T/none.jsonl" "$R")" CLAUDE_PROJECT_DIR="$R"
F="$(f s-a)"
[ "$rc" -eq 0 ] && [ -f "$F" ] && ok "written, rc 0" || bad "rc=$rc file=$F"
sha="$(git -C "$R" rev-parse HEAD)"
for k in "timestamp: " "trigger: manual" "session_id: s-a" "host: $(hostname)" "head: $sha base commit" "branch: $(git -C "$R" branch --show-current)" "plan: none" "transcript: $T/none.jsonl" "scratchpad: /tmp/claude-$(id -u)/$(printf '%s' "$R" | sed 's/[^A-Za-z0-9]/-/g')/s-a/scratchpad"; do
  has "$F" "$k" && ok "has '$k'" || bad "missing '$k'"
done
[ "$(line "$F" 'head: ')" -lt "$(line "$F" 'status')" ] && ok "header precedes the status block" || bad "status before header"
has "$F" " M a.ts" && has "$F" "?? new.spec.ts" && ok "tracked change and untracked .ts listed" || bad "status lines missing"

echo "(b) clean tree:"
R="$T/b"; repo "$R"; run "$(sid s-b)" CLAUDE_PROJECT_DIR="$R"
[ "$rc" -eq 0 ] && has "$(f s-b)" "status: clean" && ok "status: clean" || bad "clean tree: rc=$rc"

echo "(c) plans dir edge cases -> plan: none:"
R="$T/c"; repo "$R"
run "$(sid s-c1)" CLAUDE_PROJECT_DIR="$R" PRECOMPACT_PLANS_DIR="$T/no-such-dir"
[ "$rc" -eq 0 ] && has "$(f s-c1)" "plan: none" && ok "absent plans dir" || bad "absent plans dir rc=$rc"
mkdir -p "$T/empty"; run "$(sid s-c2)" CLAUDE_PROJECT_DIR="$R" PRECOMPACT_PLANS_DIR="$T/empty"
[ "$rc" -eq 0 ] && has "$(f s-c2)" "plan: none" && ok "empty plans dir" || bad "empty plans dir rc=$rc"
mkdir -p "$T/locked"; printf 'p\n' > "$T/locked/x.md"; chmod 000 "$T/locked"
run "$(sid s-c3)" CLAUDE_PROJECT_DIR="$R" PRECOMPACT_PLANS_DIR="$T/locked"; chmod 755 "$T/locked"
[ "$rc" -eq 0 ] && [ -f "$(f s-c3)" ] && ok "unreadable plans dir: rc 0, file written" || bad "unreadable plans dir rc=$rc"
mkdir -p "$T/txt"; printf 'p\n' > "$T/txt/old.md"; sleep 1; printf 'p\n' > "$T/txt/newer.txt"
run "$(sid s-c4)" CLAUDE_PROJECT_DIR="$R" PRECOMPACT_PLANS_DIR="$T/txt"
has "$(f s-c4)" "old.md" && ! has "$(f s-c4)" "newer.txt" && ok "newest non-.md file ignored" || bad "non-md plan picked"
mkdir -p "$T/sp"; printf 'p\n' > "$T/sp/my plan file.md"
run "$(sid s-c5)" CLAUDE_PROJECT_DIR="$R" PRECOMPACT_PLANS_DIR="$T/sp"
has "$(f s-c5)" "$T/sp/my plan file.md" && ok "plan filename with spaces" || bad "spaces in plan name"

echo "(d) malformed / empty stdin -> rc 0, no file:"
before="$(ls "$OUT" | wc -l)"
run "not json{" CLAUDE_PROJECT_DIR="$T/b"; [ "$rc" -eq 0 ] && [ "$(ls "$OUT" | wc -l)" = "$before" ] && ok "malformed stdin" || bad "malformed: rc=$rc"
run "" CLAUDE_PROJECT_DIR="$T/b";           [ "$rc" -eq 0 ] && [ "$(ls "$OUT" | wc -l)" = "$before" ] && ok "empty stdin" || bad "empty: rc=$rc"

echo "(e) status cap + untracked filter (PII):"
R="$T/e"; repo "$R"; for i in $(seq 1 45); do printf 'x\n' > "$R/f$i.ts"; done
printf 'x\n' > "$R/Иван Петров - фактура.pdf"; printf 'x\n' > "$R/a-notes.md"   # sorts before f*.ts, inside the cap
run "$(sid s-e)" CLAUDE_PROJECT_DIR="$R"; F="$(f s-e)"
[ "$(grep -c '^?? ' "$F")" -le 40 ] && grep -qE '^… [0-9]+ more' "$F" && ok "status capped at 40 with '… N more'" || bad "cap: $(grep -c '^?? ' "$F") lines"
! has "$F" "Петров" && ! has "$F" ".pdf" && has "$F" "1 untracked (other)" && ok "pdf name withheld, counted as other" || bad "PII name leaked or not counted"
has "$F" "?? a-notes.md" && ok ".md untracked listed" || bad ".md untracked missing"
has "$F" "… 6 more" && ok "46 listed candidates -> 40 + '… 6 more'" || bad "cap arithmetic: $(grep -F more "$F")"

echo "(f) output dir: override, slug, symlink, missing dir:"
R="$T/f/pdf_data.v2"; mkdir -p "$T/f"; repo "$R"
run "$(sid s-f1)" CLAUDE_PROJECT_DIR="$R"; [ -f "$(f s-f1)" ] && ok "PRECOMPACT_OUT_DIR honoured" || bad "override ignored"
HOMEDIR="$T/home"; mkdir -p "$HOMEDIR/.claude/projects/$(printf '%s' "$R" | sed 's/[^A-Za-z0-9]/-/g')"
out="$(printf '%s' "$(sid s-f2)" | env -u PRECOMPACT_OUT_DIR HOME="$HOMEDIR" PRECOMPACT_PLANS_DIR="$PLANS" CLAUDE_PROJECT_DIR="$R" bash "$H" 2>/dev/null)"; rc=$?
[ "$rc" -eq 0 ] && [ -f "$HOMEDIR/.claude/projects/$(printf '%s' "$R" | sed 's/[^A-Za-z0-9]/-/g')/last-compact-s-f2.md" ] && ok "slug hyphenates / _ . -> -" || bad "slug wrong: $(ls "$HOMEDIR/.claude/projects/")"
[ "$(ls "$HOMEDIR/.claude/projects/" | wc -l)" -eq 1 ] && ok "no sibling project dir created" || bad "extra dir: $(ls "$HOMEDIR/.claude/projects/")"
ln -s "$R" "$T/f/link"
mkdir -p "$HOMEDIR/.claude/projects/$(printf '%s' "$T/f/link" | sed 's/[^A-Za-z0-9]/-/g')"
out="$(printf '%s' "$(sid s-f3)" | env -u PRECOMPACT_OUT_DIR HOME="$HOMEDIR" PRECOMPACT_PLANS_DIR="$PLANS" CLAUDE_PROJECT_DIR="$T/f/link" bash "$H" 2>/dev/null)"; rc=$?
[ -f "$HOMEDIR/.claude/projects/$(printf '%s' "$T/f/link" | sed 's/[^A-Za-z0-9]/-/g')/last-compact-s-f3.md" ] && ok "symlinked project dir used as given (no realpath)" || bad "symlink resolved"
out="$(printf '%s' "$(sid s-f4)" | env -u PRECOMPACT_OUT_DIR HOME="$HOMEDIR" PRECOMPACT_PLANS_DIR="$PLANS" CLAUDE_PROJECT_DIR="$T/f/other" bash "$H" 2>/dev/null)"; rc=$?
[ "$rc" -eq 0 ] && [ ! -e "$HOMEDIR/.claude/projects/$(printf '%s' "$T/f/other" | sed 's/[^A-Za-z0-9]/-/g')" ] && ok "missing project dir: rc 0, nothing created" || bad "missing dir: rc=$rc created=$(ls "$HOMEDIR/.claude/projects/")"

echo "(g) detached HEAD:"
R="$T/g"; repo "$R"; git -C "$R" checkout -q --detach; run "$(sid s-g)" CLAUDE_PROJECT_DIR="$R"
[ "$rc" -eq 0 ] && has "$(f s-g)" "branch: detached" && ok "branch: detached" || bad "detached: rc=$rc"

echo "(h) not a git repo:"
mkdir -p "$T/h"; run "$(sid s-h)" CLAUDE_PROJECT_DIR="$T/h"
[ "$rc" -eq 0 ] && has "$(f s-h)" "git: unavailable" && has "$(f s-h)" "scratchpad: " && ok "still written with 'git: unavailable'" || bad "no-repo: rc=$rc"

echo "(i) CLAUDE_PROJECT_DIR unset:"
R="$T/i"; repo "$R"
out="$(printf '%s' "$(sid s-i1 /x.jsonl "$R")" | env -u CLAUDE_PROJECT_DIR PRECOMPACT_OUT_DIR="$OUT" PRECOMPACT_PLANS_DIR="$PLANS" bash "$H" 2>/dev/null)"; rc=$?
[ "$rc" -eq 0 ] && has "$(f s-i1)" "head: $(git -C "$R" rev-parse HEAD)" && ok "falls back to stdin cwd" || bad "cwd fallback rc=$rc"
out="$(cd "$R" && printf '{"session_id":"s-i2"}' | env -u CLAUDE_PROJECT_DIR PRECOMPACT_OUT_DIR="$OUT" PRECOMPACT_PLANS_DIR="$PLANS" bash "$H" 2>/dev/null)"; rc=$?
[ "$rc" -eq 0 ] && has "$(f s-i2)" "head: $(git -C "$R" rev-parse HEAD)" && has "$(f s-i2)" "trigger: unknown" && ok "falls back to git toplevel; trigger unknown" || bad "toplevel fallback rc=$rc"
out="$(cd "$T" && printf '{"session_id":"s-i3"}' | env -u CLAUDE_PROJECT_DIR PRECOMPACT_OUT_DIR="$OUT" PRECOMPACT_PLANS_DIR="$PLANS" bash "$H" 2>/dev/null)"; rc=$?
[ "$rc" -eq 0 ] && [ ! -f "$(f s-i3)" ] && ok "no project resolvable: rc 0, no file" || bad "unresolvable: rc=$rc file=$([ -f "$(f s-i3)" ] && echo yes)"

echo "(j) HOME unset:"
out="$(printf '%s' "$(sid s-j)" | env -u HOME -u PRECOMPACT_OUT_DIR PRECOMPACT_PLANS_DIR="$PLANS" CLAUDE_PROJECT_DIR="$T/b" bash "$H" 2>/dev/null)"; rc=$?
[ "$rc" -eq 0 ] && [ ! -f "$OUT/last-compact-s-j.md" ] && ok "HOME unset: rc 0, no file" || bad "HOME unset: rc=$rc"

echo "(k) plan resolution:"
R="$T/k"; repo "$R"; mkdir -p "$T/plans-k"; printf 'p\n' > "$T/plans-k/older-plan.md"; sleep 1; printf 'p\n' > "$T/plans-k/newest-plan.md"
TR="$T/k.jsonl"; printf '{"t":"read %s/older-plan.md"}\n{"t":"then %s/other.md"}\n{"t":"back to %s/older-plan.md again"}\n' "$T/plans-k" "$T/plans-k" "$T/plans-k" > "$TR"
run "$(sid s-k1 "$TR" "$R")" CLAUDE_PROJECT_DIR="$R" PRECOMPACT_PLANS_DIR="$T/plans-k"
has "$(f s-k1)" "plan: $T/plans-k/older-plan.md" && ! has "$(f s-k1)" "by mtime" && ok "last plan mentioned in the transcript wins" || bad "transcript plan: $(grep plan "$(f s-k1)")"
run "$(sid s-k2 "$T/none.jsonl" "$R")" CLAUDE_PROJECT_DIR="$R" PRECOMPACT_PLANS_DIR="$T/plans-k"
has "$(f s-k2)" "plan (by mtime, may be another session's): $T/plans-k/newest-plan.md" && ok "fallback newest by mtime, labelled" || bad "mtime fallback: $(grep plan "$(f s-k2)")"

echo "(l) per-session file + prune:"
old="$OUT/last-compact-ancient.md"; printf 'old\n' > "$old"; touch -d '20 days ago' "$old"
keep="$OUT/last-compact-recent.md"; printf 'recent\n' > "$keep"; touch -d '2 days ago' "$keep"
printf 'mine\n' > "$OUT/other-file.md"; touch -d '30 days ago' "$OUT/other-file.md"
run "$(sid s-l)" CLAUDE_PROJECT_DIR="$T/b"
[ -f "$(f s-l)" ] && [ -f "$(f s-b)" ] && ok "one file per session id, earlier sessions kept" || bad "per-session files"
[ ! -e "$old" ] && [ -e "$keep" ] && [ -e "$OUT/other-file.md" ] && ok "snapshots older than 14 days pruned, nothing else touched" || bad "prune: old=$([ -e "$old" ] && echo kept) keep=$([ -e "$keep" ] || echo gone) other=$([ -e "$OUT/other-file.md" ] || echo gone)"

echo "(m) wiring + hygiene:"
grep -qF 'precompact-snapshot.sh' "$HOOKS/../settings.json" && ok "registered in .claude/settings.json" || bad "not registered as a hook"
python3 - "$HOOKS/../settings.json" <<'PY' && ok "registered under PreCompact" || bad "not under the PreCompact event"
import json,sys; h=json.load(open(sys.argv[1]))["hooks"]
sys.exit(0 if any("precompact-snapshot.sh" in x["command"] for e in h.get("PreCompact",[]) for x in e["hooks"]) else 1)
PY
[ -x "$H" ] && ok "hook is executable" || bad "hook lost +x"
! grep -qE '\| *grep -q' "$H" && ok "no '| grep -q' (pipefail SIGPIPE rule)" || bad "pipes into grep -q"
! grep -qE '"decision"|exit 2' "$H" && ok "never blocks the compaction (no exit 2 / decision)" || bad "hook can block a compaction"

echo; echo "pass=$pass fail=$fail"
[ "$fail" -eq 0 ]

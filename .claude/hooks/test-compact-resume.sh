#!/usr/bin/env bash
# Regression test for .claude/hooks/compact-resume.sh (SessionStart hook, matcher "compact", MENTOR-REST
# 2026-09-18). After a compaction it prints the snapshot precompact-snapshot.sh wrote for THIS session
# (plain stdout becomes context, like the sibling SessionStart hooks), capped at 30 lines, or the newest
# other session's snapshot with a warning, or nothing. Exit 0 always. Never reads the real projects dir
# here: PRECOMPACT_OUT_DIR points at a scratch dir.

set -uo pipefail
HOOKS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
H="$HOOKS/compact-resume.sh"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
pass=0; fail=0
ok()  { printf '  ok    %s\n' "$1"; pass=$((pass+1)); }
bad() { printf '  FAIL  %s\n' "$1"; fail=$((fail+1)); }
if [ ! -f "$H" ]; then bad "hook not found: $H"; echo; echo "pass=$pass fail=$fail"; exit 1; fi

OUT="$T/out"; mkdir -p "$OUT"; rc=0
run() { out="$(printf '%s' "$1" | PRECOMPACT_OUT_DIR="$OUT" bash "$H" 2>/dev/null)"; rc=$?; }
snap() { # snap <session_id> <n-lines>
  { printf '# LAST COMPACT SNAPSHOT\ntimestamp: t\ntrigger: manual\nsession_id: %s\nhost: h\nhead: abc subject\nbranch: b\nplan: /p/%s.md\n' "$1" "$1"
    for i in $(seq 1 "$2"); do printf 'line %s\n' "$i"; done; } > "$OUT/last-compact-$1.md"
}

echo "(b) nothing to print:"
run '{"session_id":"s1","source":"compact"}'
[ "$rc" -eq 0 ] && [ -z "$out" ] && ok "no snapshot: silent, rc 0" || bad "rc=$rc out=$out"

echo "(a) own snapshot printed:"
snap s1 5; run '{"session_id":"s1","source":"compact"}'
[ "$rc" -eq 0 ] && grep -qF 'LAST COMPACT SNAPSHOT' <<< "$out" && grep -qF 'plan: /p/s1.md' <<< "$out" && ok "own session's snapshot, plain stdout" || bad "own: rc=$rc out=$out"
! grep -qF 'hookSpecificOutput' <<< "$out" && ok "not the JSON hook form" || bad "JSON form used"
! grep -qF 'another session' <<< "$out" && ok "no mismatch warning for own id" || bad "warned on own id"

echo "(c) cap at 30 lines, header survives:"
snap s2 60; run '{"session_id":"s2","source":"compact"}'
[ "$(printf '%s\n' "$out" | wc -l)" -le 30 ] && grep -qF 'head: abc subject' <<< "$out" && grep -qF 'plan: /p/s2.md' <<< "$out" && ok "≤30 lines, head + plan kept" || bad "cap: $(printf '%s\n' "$out" | wc -l) lines"
grep -qE '… [0-9]+ more line' <<< "$out" && ok "truncation announced" || bad "silent truncation"

echo "(d) another session's snapshot:"
rm -f "$OUT"/last-compact-*.md; snap s-old 3; touch -d '2 hours ago' "$OUT/last-compact-s-old.md"; snap s-new 3
run '{"session_id":"s-mine","source":"compact"}'
[ "$rc" -eq 0 ] && grep -qF 'snapshot is from another session' <<< "$out" && grep -qF 'plan: /p/s-new.md' <<< "$out" && ok "newest other snapshot, with warning" || bad "other: rc=$rc out=$out"

echo "(f) malformed stdin:"
run 'nope{'; [ "$rc" -eq 0 ] && ok "malformed stdin: rc 0" || bad "malformed: rc=$rc"
out="$(printf '' | PRECOMPACT_OUT_DIR="$T/no-such" bash "$H" 2>/dev/null)"; rc=$?
[ "$rc" -eq 0 ] && [ -z "$out" ] && ok "missing dir + empty stdin: silent, rc 0" || bad "missing dir: rc=$rc out=$out"

echo "(e) wiring + hygiene:"
python3 - "$HOOKS/../settings.json" <<'PY' && ok "registered under SessionStart with matcher 'compact'" || bad "not registered under SessionStart/compact"
import json,sys; h=json.load(open(sys.argv[1]))["hooks"]
sys.exit(0 if any(e.get("matcher")=="compact" and any("compact-resume.sh" in x["command"] for x in e["hooks"]) for e in h.get("SessionStart",[])) else 1)
PY
[ -x "$H" ] && ok "hook is executable" || bad "hook lost +x"
! grep -qE '\| *grep -q' "$H" && ok "no '| grep -q' (pipefail SIGPIPE rule)" || bad "pipes into grep -q"

echo; echo "pass=$pass fail=$fail"
[ "$fail" -eq 0 ]

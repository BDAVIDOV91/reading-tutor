#!/usr/bin/env bash
# Regression test for log-recommendation.sh. Run: bash .claude/hooks/test-log-recommendation.sh
set -u
HOOK="$(cd "$(dirname "$0")" && pwd)/log-recommendation.sh"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
pass=0; fail=0

check() { # name, condition-result(0/1)
  if [ "$2" -eq 0 ]; then pass=$((pass+1)); echo "  ok   $1"; else fail=$((fail+1)); echo "  FAIL $1"; fi
}

payload() { # tool_name, answer
  python3 - "$1" "$2" <<'PY'
import json, sys
tool, answer = sys.argv[1], sys.argv[2]
q1 = {"question": "Which path?", "header": "Path", "multiSelect": False,
      "options": [{"label": "Alpha (Recommended)", "description": "a"}, {"label": "Beta", "description": "b"}]}
q2 = {"question": "No rec here?", "header": "Plain", "multiSelect": False,
      "options": [{"label": "Yes", "description": "y"}, {"label": "No", "description": "n"}]}
print(json.dumps({"session_id": "s-test", "tool_name": tool,
                  "tool_input": {"questions": [q1, q2]},
                  "tool_response": {"questions": [q1, q2], "answers": {"Which path?": answer, "No rec here?": "Yes"}}}))
PY
}

run() { DECISION_LOG_DIR="$1" bash "$HOOK"; }
field() { python3 -c "import json,sys; rows=[json.loads(l) for l in open(sys.argv[1])]; print(rows[int(sys.argv[2])][sys.argv[3]])" "$@"; }

echo "log-recommendation hook"

# 1. Recommended pick -> two lines, first is 'recommended', second 'no_recommendation'
D="$TMP/d1"; mkdir -p "$D"
payload AskUserQuestion "Alpha (Recommended)" | run "$D"; rc=$?
check "exit 0 on normal input" "$rc"
[ "$(wc -l < "$D/decision-log.jsonl")" -eq 2 ]; check "one line per answered question" $?
[ "$(field "$D/decision-log.jsonl" 0 picked_kind)" = "recommended" ]; check "recommended pick classified" $?
[ "$(field "$D/decision-log.jsonl" 1 picked_kind)" = "no_recommendation" ]; check "question without a recommendation classified" $?
[ -n "$(field "$D/decision-log.jsonl" 0 host)" ]; check "host recorded" $?

# 2. Other listed option
D="$TMP/d2"; mkdir -p "$D"
payload AskUserQuestion "Beta" | run "$D"
[ "$(field "$D/decision-log.jsonl" 0 picked_kind)" = "other_option" ]; check "other listed option classified" $?

# 3. Own free text
D="$TMP/d3"; mkdir -p "$D"
payload AskUserQuestion "use /decide instead" | run "$D"
[ "$(field "$D/decision-log.jsonl" 0 picked_kind)" = "own_text" ]; check "own text classified" $?

# 4. Log dir absent -> no file created, notice emitted, exit 0
D="$TMP/absent"
out="$(payload AskUserQuestion "Alpha (Recommended)" | run "$D")"; rc=$?
check "exit 0 when log dir absent" "$rc"
[ ! -e "$D" ]; check "log dir is never created" $?
printf '%s' "$out" | grep -q "decision NOT logged"; check "skip is announced, not silent" $?

# 5. Malformed stdin -> exit 0, nothing written
D="$TMP/d5"; mkdir -p "$D"
printf 'not json{' | run "$D"; rc=$?
check "exit 0 on malformed input" "$rc"
[ ! -e "$D/decision-log.jsonl" ]; check "nothing written on malformed input" $?

# 6. Other tool -> ignored
D="$TMP/d6"; mkdir -p "$D"
payload Bash "Alpha (Recommended)" | run "$D"
[ ! -e "$D/decision-log.jsonl" ]; check "non-AskUserQuestion tool ignored" $?

# 7. Appends, never truncates
D="$TMP/d7"; mkdir -p "$D"
payload AskUserQuestion "Beta" | run "$D"; payload AskUserQuestion "Beta" | run "$D"
[ "$(wc -l < "$D/decision-log.jsonl")" -eq 4 ]; check "appends across calls" $?

# 8. S5 / CF2-4: confidence lives in the recommended option's DESCRIPTION; the label stays exact
confpayload() { # description of the recommended option
  python3 - "$1" <<'PY2'
import json, sys
q = {"question": "Conf?", "header": "Conf", "multiSelect": False,
     "options": [{"label": "Alpha (Recommended)", "description": sys.argv[1]}, {"label": "Beta", "description": "b"}]}
print(json.dumps({"session_id": "s-test", "tool_name": "AskUserQuestion",
                  "tool_input": {"questions": [q]},
                  "tool_response": {"questions": [q], "answers": {"Conf?": "Alpha (Recommended)"}}}))
PY2
}
D="$TMP/d8"; mkdir -p "$D"
confpayload "Smallest change, reversible. ~70%" | run "$D"
[ "$(field "$D/decision-log.jsonl" 0 picked_kind)" = "recommended" ]; check "exact label with % in description still recommended" $?
[ "$(field "$D/decision-log.jsonl" 0 confidence)" = "70" ]; check "confidence parsed from description" $?
D="$TMP/d8b"; mkdir -p "$D"
confpayload "Keeps coverage at 88% without the tilde" | run "$D"
[ "$(field "$D/decision-log.jsonl" 0 confidence)" = "None" ]; check "a bare percentage is not a confidence" $?
D="$TMP/d8c"; mkdir -p "$D"
payload AskUserQuestion "Alpha (Recommended)" | run "$D"
[ "$(field "$D/decision-log.jsonl" 0 confidence)" = "None" ]; check "no % gives confidence null" $?
[ "$(field "$D/decision-log.jsonl" 1 confidence)" = "None" ]; check "no recommendation gives confidence null" $?

# 9. D3: a multi-select answer is one joined string; a pick that includes the Recommended option is not own_text
mspayload() { # answer string
  python3 - "$1" <<'PY2'
import json, sys
q = {"question": "Which slices?", "header": "Slices", "multiSelect": True,
     "options": [{"label": "#1, 2 go into S4 (Recommended)", "description": "x ~80%"},
                 {"label": "Cleanup now", "description": "c"}, {"label": "Later", "description": "l"}]}
print(json.dumps({"session_id": "s-test", "tool_name": "AskUserQuestion",
                  "tool_input": {"questions": [q]},
                  "tool_response": {"questions": [q], "answers": {"Which slices?": sys.argv[1]}}}))
PY2
}
D="$TMP/d9"; mkdir -p "$D"
mspayload '"#1, 2 go into S4 (Recommended)", Cleanup now' | run "$D"
[ "$(field "$D/decision-log.jsonl" 0 picked_kind)" = "recommended" ]; check "multi-select including Recommended (quoted, comma label) -> recommended" $?
[ "$(field "$D/decision-log.jsonl" 0 confidence)" = "80" ]; check "multi-select confidence parsed" $?
D="$TMP/d9b"; mkdir -p "$D"
mspayload 'Cleanup now, Later' | run "$D"
[ "$(field "$D/decision-log.jsonl" 0 picked_kind)" = "other_option" ]; check "multi-select of listed non-recommended options -> other_option" $?
D="$TMP/d9c"; mkdir -p "$D"
mspayload 'Cleanup now, do it my way' | run "$D"
[ "$(field "$D/decision-log.jsonl" 0 picked_kind)" = "own_text" ]; check "multi-select with free text and no Recommended -> own_text" $?
D="$TMP/d9d"; mkdir -p "$D"
mspayload '#1, 2 go into S4 (Recommended)' | run "$D"
[ "$(field "$D/decision-log.jsonl" 0 picked_kind)" = "recommended" ]; check "multi-select with only the Recommended option (unquoted) -> recommended" $?

echo "pass=$pass fail=$fail"
[ "$fail" -eq 0 ]

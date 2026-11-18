#!/usr/bin/env bash
# PostToolUse(AskUserQuestion) hook: record each answered question and whether the "(Recommended)"
# option was picked, so recommendation accuracy can be measured later. Logic lives in
# log_recommendation.py beside this file. Always exits 0 — it must never break a tool call.
# Test: bash .claude/hooks/test-log-recommendation.sh
python3 "$(dirname "$0")/log_recommendation.py" 2>/dev/null || true
exit 0

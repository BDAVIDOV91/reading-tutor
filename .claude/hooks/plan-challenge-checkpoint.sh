#!/usr/bin/env bash
# PostToolUse(ExitPlanMode) hook: after a plan is approved, inject the standing
# "challenge or proceed?" checkpoint instruction. This hook does NOT spawn anything —
# it reliably reminds the main loop to run the user-gated challenger gate before coding.
# The plan path comes from the hook payload (tool_response.filePath, then tool_input.planFilePath):
# ~/.claude/plans/ is shared by every session, so "the newest plan" can be another session's.
# A plan whose '## Challenger Findings' section already records both verdicts gets a short note instead
# of the question (2026-10-08 retro).
# Test: bash .claude/hooks/test-plan-challenge-checkpoint.sh
input="$(cat)"
tool="$(printf '%s' "$input" | python3 -c "import sys,json;
try: print(json.load(sys.stdin).get('tool_name',''))
except Exception: print('')" 2>/dev/null)"
case "$tool" in
  *ExitPlanMode*)
    HOOK_INPUT="$input" python3 - <<'PY'
import json, os, re

def plan_path():
    try:
        data = json.loads(os.environ.get("HOOK_INPUT", ""))
    except ValueError:
        return ""
    for key, field in (("tool_response", "filePath"), ("tool_input", "planFilePath")):
        block = data.get(key) if isinstance(data, dict) else None
        value = block.get(field) if isinstance(block, dict) else None
        if isinstance(value, str) and value:
            return value
    return ""

VERDICT = re.compile(r"\b(APPROVE|REVISE|REJECT)[A-Z]*\b")


def already_challenged(path):
    """True when the plan's '## Challenger Findings' section records BOTH verdicts (2026-10-08 retro).

    Both = the heading says 'both <VERDICT>', or the section (to the next '## ') holds 2+ verdict words.
    Unreadable or missing plan -> False, so the checkpoint question is asked (fail toward asking).
    """
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            text = handle.read(1 << 20)
    except OSError:
        return False
    for match in re.finditer(r"^## Challenger Findings\b[^\n]*$", text, flags=re.M):
        heading = match.group(0)
        rest = text[match.end():]
        nxt = re.search(r"^## ", rest, flags=re.M)
        section = heading + (rest[: nxt.start()] if nxt else rest)
        if re.search(r"\bboth\b[^\n]*" + VERDICT.pattern, heading, flags=re.I) or len(VERDICT.findall(section)) >= 2:
            return True
    return False


path = plan_path()
if path and already_challenged(path):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PostToolUse",
        "additionalContext": (
            "PLAN-CHALLENGE CHECKPOINT: plan already challenged (both verdicts recorded under "
            "'## Challenger Findings' in " + path + "). Do not ask Challenge/Proceed again; proceed. "
            "If the plan changed materially since those verdicts, say so and offer a re-challenge. "
            "Then build the native task list from the plan's Steps (TaskCreate) and keep it updated."
        )}}))
    raise SystemExit(0)
where = path or (
    "the path from the ExitPlanMode result line 'Your plan has been saved to:' "
    "(never pick a plan by mtime: ~/.claude/plans/ is shared by every session)"
)
msg = (
    "PLAN-CHALLENGE CHECKPOINT (project workflow). The plan is approved. "
    "BEFORE writing any implementation code, ask the user with AskUserQuestion: "
    "\"Challenge the plan or proceed?\" (options: Challenge / Proceed; the recommended one FIRST, "
    "labelled \"(Recommended)\", with the reason).\n"
    "- If Challenge: spawn TWO 'challenger' subagents IN PARALLEL (Agent tool, "
    "subagent_type: challenger), each given the plan file path: " + where + ". When BOTH return, "
    "post a combined summary of their findings + both approve/revise verdicts, then MERGE the findings "
    "into the existing plan file: append a '## Challenger Findings (A: <VERDICT>, B: <VERDICT>)' section "
    "(that heading lets a later re-approval skip this question) and fold any accepted "
    "fixes inline where they apply (never overwrite/replace the original plan). Then proceed.\n"
    "- If Proceed: implement directly, no challenge.\n"
    "Either way (Challenge after the merge, or Proceed): then build the native task list from the plan's "
    "Steps (TaskCreate) and keep it updated."
)
print(json.dumps({"hookSpecificOutput": {
    "hookEventName": "PostToolUse",
    "additionalContext": msg}}))
PY
    ;;
esac
exit 0

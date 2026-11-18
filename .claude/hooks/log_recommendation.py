#!/usr/bin/env python3
"""PostToolUse(AskUserQuestion): append one line per answered question to the decision log.

Purpose: measure whether a "(Recommended)" option was actually the right call, not just how often it
was picked. Outcomes are marked later in decision-outcomes.jsonl (see decision-log-report.sh).

Rules:
- Never fails the tool call: every error path exits 0.
- Writes ONLY if the log directory already exists; never creates it, so a host without
  the Claude project dir skips instead of collecting question text. A skip is announced back to the model, never silent.
- No network. Free-text answers may contain anything the owner typed, including secrets; the log
  lives outside the repo for that reason and must never be committed.
- Rejected or interrupted questions do not fire PostToolUse, so they are not captured.
- Confidence (S5, CF2-4): the label stays exactly "... (Recommended)"; the stated certainty lives in
  that option's description as "~70%" and is logged as `confidence` (null when absent). The tilde is
  required so an unrelated "88% coverage" is never read as a confidence.
- Multi-select (D3): the answer arrives as one comma-joined string, with labels that contain a comma
  wrapped in double quotes. It is split before classifying, so a pick that includes the Recommended
  option is "recommended", not "own_text".
"""

import csv
import datetime
import hashlib
import json
import os
import re
import socket
import sys

DEFAULT_DIR = os.path.expanduser(
    "~/.claude/projects/-home-technojihad-reading-tutor"
)


def notice(text):
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "additionalContext": text,
                }
            }
        )
    )


CONFIDENCE_RE = re.compile(r"(?<![\w.])~\s?(\d{1,3})\s?%")


def confidence_of(description):
    match = CONFIDENCE_RE.search(description if isinstance(description, str) else "")
    if not match:
        return None
    value = int(match.group(1))
    return value if value <= 100 else None


def picked_parts(picked, labels, multi_select):
    """The labels (or free-text pieces) an answer names. Single-select answers are never split."""
    if not isinstance(picked, str):
        return []
    if not multi_select or picked in labels:
        return [picked]
    try:
        row = next(csv.reader([picked], skipinitialspace=True))
    except (csv.Error, StopIteration):
        return [picked]
    return [part.strip() for part in row if part.strip()]


def classify(picked, labels, recommended_labels, multi_select):
    if not recommended_labels:
        return "no_recommendation"
    parts = picked_parts(picked, labels, multi_select)
    if any(part in recommended_labels for part in parts):
        return "recommended"
    if parts and all(part in labels for part in parts):
        return "other_option"
    return "own_text"


def as_dict(value):
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except ValueError:
            return {}
    return {}


def main():
    try:
        data = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        return
    if not isinstance(data, dict) or data.get("tool_name") != "AskUserQuestion":
        return

    log_dir = os.environ.get("DECISION_LOG_DIR", DEFAULT_DIR)
    if not os.path.isdir(log_dir):
        notice(
            "decision NOT logged — log dir absent on this host (%s)"
            % socket.gethostname()
        )
        return

    tool_input = as_dict(data.get("tool_input"))
    tool_response = as_dict(data.get("tool_response"))
    answers = tool_response.get("answers") or tool_input.get("answers") or {}
    questions = tool_input.get("questions") or tool_response.get("questions") or []
    if not isinstance(answers, dict) or not isinstance(questions, list):
        return

    ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
    session_id = str(data.get("session_id", ""))
    lines = []
    for q in questions:
        if not isinstance(q, dict):
            continue
        text = q.get("question", "")
        if text not in answers:
            continue
        options = [o for o in q.get("options", []) if isinstance(o, dict)]
        labels = [o.get("label", "") for o in options]
        rec_options = [o for o in options if "(Recommended)" in o.get("label", "")]
        recommended = rec_options[0].get("label", "") if rec_options else None
        multi_select = bool(q.get("multiSelect", False))
        picked = answers[text]
        kind = classify(
            picked, labels, [o.get("label", "") for o in rec_options], multi_select
        )
        confidence = (
            confidence_of(rec_options[0].get("description")) if rec_options else None
        )
        qid = hashlib.sha1((session_id + ts + text).encode("utf-8")).hexdigest()[:12]
        lines.append(
            json.dumps(
                {
                    "id": qid,
                    "ts": ts,
                    "session_id": session_id,
                    "host": socket.gethostname(),
                    "header": q.get("header", ""),
                    "question": text,
                    "options": labels,
                    "multi_select": multi_select,
                    "recommended": recommended,
                    "confidence": confidence,
                    "picked": picked,
                    "picked_kind": kind,
                },
                ensure_ascii=False,
            )
        )

    if lines:
        with open(
            os.path.join(log_dir, "decision-log.jsonl"), "a", encoding="utf-8"
        ) as fh:
            fh.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001 — a logging hook must never break the tool call
        pass
    sys.exit(0)

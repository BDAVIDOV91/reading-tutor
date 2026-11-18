#!/usr/bin/env bash
# SessionStart hook, matcher "compact" (MENTOR-REST, 2026-09-18): after a compaction, print the snapshot
# precompact-snapshot.sh wrote for THIS session, so the resumed session starts from HEAD / status /
# plan path evidence, not from the summary alone. Plain stdout becomes context (same convention as
# skills-drift-check.sh and graphify-staleness.sh). Capped at 30 lines; the header (host, head, branch,
# plan) comes first in the file, so the cap only drops status lines. If this session has no snapshot
# but another one does, prints the newest with a warning. Silent otherwise. Exit 0 always.
# Override for the test: PRECOMPACT_OUT_DIR.  Test: bash .claude/hooks/test-compact-resume.sh
HOOK_INPUT="$(cat 2>/dev/null)"
export HOOK_INPUT
python3 - <<'PY' 2>/dev/null || true
import glob, json, os, re, subprocess, sys

try:
    d = json.loads(os.environ.get("HOOK_INPUT", "") or "{}")
except Exception:
    d = {}
if not isinstance(d, dict):
    d = {}
sid = re.sub(r"[^A-Za-z0-9_-]", "-", str(d.get("session_id") or ""))

out_dir = os.environ.get("PRECOMPACT_OUT_DIR")
if not out_dir:
    proj = os.environ.get("CLAUDE_PROJECT_DIR") or ""
    if not proj:
        try:
            r = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, timeout=10)
            proj = r.stdout.strip() if r.returncode == 0 else ""
        except (OSError, subprocess.SubprocessError):
            proj = ""
    home = os.environ.get("HOME")
    if not proj or not home:
        sys.exit(0)
    out_dir = os.path.join(home, ".claude", "projects", re.sub(r"[^A-Za-z0-9]", "-", proj))
if not os.path.isdir(out_dir):
    sys.exit(0)

own = os.path.join(out_dir, "last-compact-%s.md" % sid) if sid else ""
if own and os.path.isfile(own):
    path, warn = own, ""
else:
    cands = [p for p in glob.glob(os.path.join(out_dir, "last-compact-*.md")) if os.path.isfile(p)]
    if not cands:
        sys.exit(0)
    path = max(cands, key=os.path.getmtime)
    warn = " — snapshot is from another session (%s); this session's was not written" % os.path.basename(path)

try:
    body = [l.rstrip("\n") for l in open(path, encoding="utf-8", errors="replace")]
except OSError:
    sys.exit(0)
if body and body[0].startswith("# LAST COMPACT SNAPSHOT"):
    body = body[1:]
out = ["LAST COMPACT SNAPSHOT (%s)%s — a snapshot at compaction time; git is the truth:" % (path, warn)]
room = 30 - 1 - (1 if len(body) > 28 else 0)
out.extend(body[:room])
if len(body) > room:
    out.append("… %d more line(s) in %s" % (len(body) - room, path))
print("\n".join(out))
PY
exit 0

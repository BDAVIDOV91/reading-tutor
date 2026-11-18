#!/usr/bin/env bash
# PreCompact hook (MENTOR-REST, 2026-09-18, idea from the mentor's context-continuation rule): before a
# compaction, write a resume snapshot the post-compaction session can trust more than its summary:
# host, HEAD, branch, working-tree status (filenames only), the plan file this session used, the
# transcript and scratchpad paths. Written to ~/.claude/projects/<slug>/last-compact-<session_id>.md,
# one file per session (sessions share one tree), pruned after 14 days. Read back by compact-resume.sh
# (SessionStart, matcher "compact") and by the session-recovery skill.
#
# Slug rule: every character outside [A-Za-z0-9] becomes "-" (that is how Claude Code names the dir:
# /home/x/pdf_data_extractor_v2 -> -home-x-pdf-data-extractor-v2). The project dir must already exist;
# the hook never creates one. Untracked names are listed only for code/doc extensions, so a client's
# document name never lands here (PII). Always exits 0: a non-zero code would block the compaction.
# Overrides for the test: PRECOMPACT_OUT_DIR, PRECOMPACT_PLANS_DIR.
# Test: bash .claude/hooks/test-precompact-snapshot.sh
HOOK_INPUT="$(cat 2>/dev/null)"
export HOOK_INPUT
python3 - <<'PY' 2>/dev/null || true
import datetime, glob, json, os, re, subprocess, sys, time

try:
    d = json.loads(os.environ.get("HOOK_INPUT", ""))
except Exception:
    sys.exit(0)
if not isinstance(d, dict):
    sys.exit(0)

def git(root, *args):
    try:
        r = subprocess.run(["git", "-C", root, *args], capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.rstrip("\n") if r.returncode == 0 else None

sid = re.sub(r"[^A-Za-z0-9_-]", "-", str(d.get("session_id") or "unknown"))
trigger = str(d.get("trigger") or "unknown")
transcript = str(d.get("transcript_path") or "")

proj = os.environ.get("CLAUDE_PROJECT_DIR") or str(d.get("cwd") or "")
if not proj:
    proj = git(os.getcwd(), "rev-parse", "--show-toplevel") or ""
if not proj:
    sys.exit(0)
slug = re.sub(r"[^A-Za-z0-9]", "-", proj)          # as given: no realpath, matches Claude Code's slug

out_dir = os.environ.get("PRECOMPACT_OUT_DIR")
if not out_dir:
    home = os.environ.get("HOME")
    if not home:
        sys.exit(0)
    out_dir = os.path.join(home, ".claude", "projects", slug)
if not os.path.isdir(out_dir):
    sys.exit(0)

lines = ["# LAST COMPACT SNAPSHOT",
         "timestamp: " + datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
         "trigger: " + trigger, "session_id: " + sid, "host: " + os.uname().nodename]

head = git(proj, "rev-parse", "HEAD")
if head:
    lines.append("head: %s %s" % (head, git(proj, "log", "-1", "--format=%s") or ""))
    lines.append("branch: " + (git(proj, "branch", "--show-current") or "detached"))
else:
    lines.append("git: unavailable")

# Plan: the last ~/.claude/plans/<name>.md this session's transcript mentions; else newest by mtime.
plans_dir = os.environ.get("PRECOMPACT_PLANS_DIR") or os.path.join(os.environ.get("HOME", "/nonexistent"), ".claude", "plans")
plan = None
if transcript and os.path.isfile(transcript):
    try:
        with open(transcript, "rb") as f:
            f.seek(0, 2); size = f.tell(); f.seek(max(0, size - 5_000_000)); tail = f.read().decode("utf-8", "replace")
        dirs = {plans_dir.rstrip("/"), os.path.expanduser("~/.claude/plans"), "~/.claude/plans"}
        pat = "(?:%s)/[^\\s\"'`\\\\]+?\\.md" % "|".join(re.escape(x) for x in dirs)
        for m in reversed(re.findall(pat, tail)):
            cand = os.path.expanduser(m)
            if os.path.isfile(cand):
                plan = "plan: " + cand
                break
    except OSError:
        pass
if plan is None:
    try:
        cands = [p for p in glob.glob(os.path.join(plans_dir, "*.md")) if os.path.isfile(p)]
        newest = max(cands, key=os.path.getmtime) if cands else None
    except OSError:
        newest = None
    plan = "plan (by mtime, may be another session's): " + newest if newest else "plan: none"
lines.append(plan)
lines.append("transcript: " + (transcript or "none"))
lines.append("scratchpad: /tmp/claude-%d/%s/%s/scratchpad" % (os.getuid(), slug, sid))

if head:
    KEEP = {".ts", ".tsx", ".js", ".mjs", ".py", ".sh", ".md", ".json", ".yml", ".yaml", ".sql", ".prisma"}
    status = git(proj, "status", "--short") or ""
    shown, other = [], 0
    for s in status.splitlines():
        if s.startswith("??") and os.path.splitext(s[3:].strip().strip('"'))[1].lower() not in KEEP:
            other += 1
        else:
            shown.append(s)
    if not shown and not other:
        lines.append("status: clean")
    else:
        lines.append("status:")
        lines.extend(shown[:40])
        if len(shown) > 40:
            lines.append("… %d more" % (len(shown) - 40))
        if other:
            lines.append("%d untracked (other)" % other)

cutoff = time.time() - 14 * 86400
for old in glob.glob(os.path.join(out_dir, "last-compact-*.md")):
    try:
        if os.path.getmtime(old) < cutoff:
            os.remove(old)
    except OSError:
        pass

target = os.path.join(out_dir, "last-compact-%s.md" % sid)
tmp = target + ".tmp"
try:
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    os.replace(tmp, target)
except OSError:
    try: os.remove(tmp)
    except OSError: pass
PY
exit 0

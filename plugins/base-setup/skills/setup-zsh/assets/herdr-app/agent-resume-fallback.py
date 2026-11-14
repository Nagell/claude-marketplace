#!/usr/bin/env python3
"""Point a Herdr terminal's agent-resume label back at the conversation a Claude Code
restart replaced.

herdr-agent-resume notes each new Claude Code session in the terminal's `agent-resume`
label. Restarting Claude in a tab overwrites that label with a session that has no
transcript until its first message, so a reboot before that message loses the real
conversation ("no saved conversation to resume").

For each terminal whose agent is lost (another boot or another shell) and whose label
points at a Claude session with no transcript, this reads the mod's log. When the
terminal's last "forgot <id>" was followed within RESTART_WINDOW seconds by the "saved"
hook that wrote the current label (a restart, not a quit), and <id>'s transcript exists
in the same project folder, it rewrites the label to <id>, keeping every other field.
Anything else is left alone.

  python3 -I agent-resume-fallback.py [--dry-run] [TERMINAL...]

No terminal: every live terminal. Standard library only.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import time

LABEL = "agent-resume"
RESTART_WINDOW = 120  # seconds between "forgot" and the next "saved" hook
SESSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{7,127}$")


def data_dir():
    app = os.environ.get("HERDR_APP_HOME") or os.path.expanduser("~/.config/herdr-app")
    return os.path.join(app, "data", "agent-resume")


def hc(*args):
    hc_bin = shutil.which("hc") or os.path.expanduser("~/.local/bin/hc")
    r = subprocess.run([hc_bin, *args], capture_output=True, text=True, timeout=10)
    if r.returncode != 0:
        raise RuntimeError(f"hc {args[0]}: {(r.stderr or r.stdout).strip()}")
    return r.stdout


def boot_id():
    try:
        with open("/proc/sys/kernel/random/boot_id") as f:
            return f.read().strip() or None
    except OSError:
        return None


def read_log(path):
    events = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                if isinstance(event, dict):
                    events.append(event)
    except OSError:
        pass
    return events


def seconds(stamp):
    return time.mktime(time.strptime(stamp, "%Y-%m-%dT%H:%M:%S"))


def replaced_session(events, term):
    """The session a quick restart in `term` replaced, or None when unsure."""
    mine = [e for e in events if e.get("terminal") == term]
    forgot = [i for i, e in enumerate(mine) if e.get("event") == "watch"
              and str(e.get("outcome", "")).startswith("forgot ")]
    saved = [i for i, e in enumerate(mine) if e.get("event") == "hook" and e.get("outcome") == "saved"]
    if not forgot or not saved:
        return None
    last_forgot, last_saved = forgot[-1], saved[-1]
    # The current label must come from the first "saved" after the last "forgot".
    if last_saved < last_forgot or any(last_forgot < i < last_saved for i in saved):
        return None
    try:
        gap = seconds(mine[last_saved]["at"]) - seconds(mine[last_forgot]["at"])
    except (KeyError, TypeError, ValueError):
        return None
    if not 0 <= gap <= RESTART_WINDOW:
        return None
    session = mine[last_forgot]["outcome"].split(" ", 1)[1]
    return session if SESSION_RE.fullmatch(session) else None


def fix(terminal, events, boot, file_ok=os.path.isfile):
    """(new label text, old session, new session) for this `hc get` record, or None."""
    raw = (terminal.get("labels") or {}).get(LABEL)
    if not raw or terminal.get("state") != "live":
        return None
    try:
        label = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(label, dict) or label.get("agent") != "claude":
        return None
    transcript = label.get("transcript")
    if not isinstance(transcript, str) or not os.path.isabs(transcript) or file_ok(transcript):
        return None
    lost = (boot and label.get("boot") and label["boot"] != boot) or terminal.get("pid") != label.get("shell")
    if not lost:
        return None  # the agent still runs there: its label is current
    old = replaced_session(events, terminal.get("address"))
    if not old or old == label.get("session"):
        return None
    old_transcript = os.path.join(os.path.dirname(transcript), old + ".jsonl")
    if not file_ok(old_transcript):
        return None
    new = dict(label, session=old, transcript=old_transcript)
    return json.dumps(new, separators=(",", ":"), ensure_ascii=False), label.get("session"), old


def log(**fields):
    try:
        os.makedirs(data_dir(), exist_ok=True)
        line = json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), **fields}, ensure_ascii=False)
        with open(os.path.join(data_dir(), "fallback.jsonl"), "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def main(argv):
    dry_run = "--dry-run" in argv
    terms = [a for a in argv[1:] if a != "--dry-run"]
    try:
        if not terms:
            listed = json.loads(hc("ls", "--json"))
            rows = listed.get("terminals", []) if isinstance(listed, dict) else listed
            terms = [t["address"] for t in rows if t.get("state") == "live" and "/" not in t["address"]]
        terminals = [json.loads(hc("get", t, "--json")) for t in terms]
    except (RuntimeError, OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"agent-resume-fallback: {error}", file=sys.stderr)
        return 0
    events = read_log(os.path.join(data_dir(), "log.jsonl"))
    boot = boot_id()
    changes = []
    for terminal in terminals:
        found = fix(terminal, events, boot)
        if not found:
            continue
        text, was, now = found
        term = terminal["address"]
        changes.append({"terminal": term, "from": was, "to": now})
        if dry_run:
            continue
        try:
            hc("label", term, f"{LABEL}={text}")
            log(terminal=term, outcome="restored", session=now, replaced=was)
        except (RuntimeError, OSError, subprocess.SubprocessError) as error:
            log(terminal=term, outcome=f"error: {error}", session=now, replaced=was)
    if dry_run:
        print(json.dumps({"dry_run": True, "would_restore": changes}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

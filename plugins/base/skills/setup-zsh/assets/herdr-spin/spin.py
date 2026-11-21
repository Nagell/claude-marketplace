#!/usr/bin/env python3
"""Own the agent status glyph in herdr's sidebar, animated while an agent works.

Herdr dropped its built-in spinner in 0.8.0 and exposes no setting to restore it, and its
`state_icon` cannot animate, so this replaces that column with metadata tokens the sidebar
renders instead. One token per state, because a token carries a single fixed colour and
the row config is where that colour lives:

    $w  working   animated braille   $d  done     ✓
    $b  blocked   ◉                  $i  idle     ○ (and · for unknown)

Exactly one is set per pane and the rest are cleared, so a row shows a single glyph.
Set HERDR_SPIN_FRAME_MS to change the cadence; the default is 120ms.

Run with --restart to replace an animator that is already running, or --stop to clear the
glyphs and leave.
"""

from __future__ import annotations

import fcntl
import json
import os
import signal
import socket
import sys
import time

SOURCE = "herdr-spin"
FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
WORKING = "working"
TOKENS = ("w", "b", "d", "i")
STATE_TOKEN = {"working": "w", "blocked": "b", "done": "d", "idle": "i", "unknown": "i"}
STATE_GLYPH = {"blocked": "◉", "done": "✓", "idle": "○", "unknown": "·"}
DEFAULT_FRAME_MS = 120
MIN_FRAME_MS = 40
MAX_FRAME_MS = 2000
POLL_MS = 500
MAX_CONSECUTIVE_FAILURES = 20
# Fixed, so a hand-started run and the plugin's own hook collide instead of both painting.
RUNTIME_DIR = "/tmp/herdr-spin-%d" % os.getuid()
LOCK_PATH = os.path.join(RUNTIME_DIR, "spin.lock")
STOP_PATH = os.path.join(RUNTIME_DIR, "stop")

_stop = False


def request(sock_path: str, method: str, params: dict) -> dict | None:
    """Run one request against herdr, or return None if the socket is unusable.

    Herdr answers a single request per connection and then closes it, so every call opens
    its own. A malformed request is answered with an error and the same close, which is
    why only known-good parameter shapes go through here.
    """
    payload = json.dumps({"id": SOURCE, "method": method, "params": params}) + "\n"
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(5)
            sock.connect(sock_path)
            with sock.makefile("rwb") as io:
                io.write(payload.encode())
                io.flush()
                line = io.readline()
    except (OSError, socket.timeout):
        return None
    if not line:
        return None
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        return {}


def fetch_agents(sock_path: str) -> dict[str, str] | None:
    """Return pane id to agent status, or None when herdr cannot be reached."""
    message = request(sock_path, "agent.list", {})
    if message is None:
        return None
    result = message.get("result")
    if not isinstance(result, dict) or result.get("type") != "agent_list":
        return None
    return {
        agent["pane_id"]: agent.get("agent_status", "unknown")
        for agent in result.get("agents", [])
        if agent.get("pane_id")
    }


def paint(sock_path: str, pane: str, token: str | None, glyph: str, ttl_ms: int | None) -> None:
    """Set one state token on a pane and clear the other three.

    The working frame also goes out as a state label, which is the only way into the
    session navigator: it has no row config, but its state text shows a reported label.
    """
    tokens = dict.fromkeys(TOKENS, None)
    if token is not None:
        tokens[token] = glyph
    params = {"pane_id": pane, "source": SOURCE, "tokens": tokens}
    if token == "w":
        params["state_labels"] = {WORKING: glyph}
    else:
        params["clear_state_labels"] = True
    if ttl_ms is not None:
        params["ttl_ms"] = ttl_ms
    request(sock_path, "pane.report_metadata", params)


def frame_interval() -> float:
    """Seconds between frames, clamped so a bad override cannot flood the socket."""
    try:
        requested = int(os.environ.get("HERDR_SPIN_FRAME_MS", ""))
    except ValueError:
        requested = DEFAULT_FRAME_MS
    return max(MIN_FRAME_MS, min(requested, MAX_FRAME_MS)) / 1000.0


def daemonize(log_path: str) -> None:
    """Detach into the background so the one-shot startup hook can return."""
    if os.fork() > 0:
        os._exit(0)
    os.setsid()
    if os.fork() > 0:
        os._exit(0)
    null = os.open(os.devnull, os.O_RDONLY)
    os.dup2(null, 0)
    os.close(null)
    log = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    os.dup2(log, 1)
    os.dup2(log, 2)
    os.close(log)


def acquire_lock():
    """Claim sole ownership and record the pid, or return None.

    A live handoff runs the startup hook again, so without this a second animator would
    fight the first over the same tokens and the frames would flicker.
    """
    os.makedirs(RUNTIME_DIR, exist_ok=True)
    handle = open(LOCK_PATH, "r+" if os.path.exists(LOCK_PATH) else "w+")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        return None
    handle.seek(0)
    handle.truncate()
    handle.write("%d\n" % os.getpid())
    handle.flush()
    return handle


def lock_held() -> bool:
    """Whether an animator currently owns the lock."""
    try:
        handle = open(LOCK_PATH)
    except OSError:
        return False
    with handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_SH | fcntl.LOCK_NB)
            return False
        except OSError:
            return True


def request_stop(timeout: float = 5.0) -> None:
    """Ask a running animator to exit, then wait for it to drop the lock.

    A flag file rather than a signal: a hand-started run and the plugin hook can end up in
    different PID namespaces, where neither side can signal the other's pid, but both see
    the same file.
    """
    os.makedirs(RUNTIME_DIR, exist_ok=True)
    open(STOP_PATH, "w").close()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline and lock_held():
        time.sleep(0.1)
    try:
        os.remove(STOP_PATH)
    except OSError:
        pass


def animate(sock_path: str) -> None:
    """Advance one frame per interval, until herdr goes away.

    Only working panes are repainted every frame; the rest are written once when their
    state changes, so idle rows do not trigger a sidebar redraw eight times a second.
    """
    interval = frame_interval()
    # Outlive several frames but still expire, so a crash cannot strand a frame on a row.
    ttl_ms = max(1000, int(interval * 1000) * 8)
    poll_every = max(1, round(POLL_MS / (interval * 1000)))
    agents: dict[str, str] = {}
    painted: dict[str, str] = {}
    failures = 0
    index = 0

    while not _stop and not os.path.exists(STOP_PATH):
        if index % poll_every == 0:
            polled = fetch_agents(sock_path)
            if polled is None:
                failures += 1
                if failures >= MAX_CONSECUTIVE_FAILURES:
                    return
            else:
                failures = 0
                agents = polled
        frame = FRAMES[index % len(FRAMES)]
        index += 1
        for pane, status in agents.items():
            if status == WORKING:
                paint(sock_path, pane, "w", frame, ttl_ms)
            elif painted.get(pane) != status:
                token = STATE_TOKEN.get(status, "i")
                paint(sock_path, pane, token, STATE_GLYPH.get(status, "·"), None)
        painted = dict(agents)
        time.sleep(interval)

    for pane in painted:
        paint(sock_path, pane, None, "", None)


def handle_stop(*_args) -> None:
    global _stop
    _stop = True


def main() -> int:
    if "--stop" in sys.argv:
        request_stop()
        return 0
    if "--restart" in sys.argv:
        request_stop()

    sock_path = os.environ.get("HERDR_SOCKET_PATH")
    if not sock_path:
        print("HERDR_SOCKET_PATH is unset; run this from a herdr pane or plugin hook",
              file=sys.stderr)
        return 1

    state_dir = os.environ.get("HERDR_PLUGIN_STATE_DIR") or RUNTIME_DIR
    os.makedirs(state_dir, exist_ok=True)
    if os.environ.get("HERDR_SPIN_FOREGROUND") != "1":
        daemonize(os.path.join(state_dir, "spin.log"))

    handle = acquire_lock()
    if handle is None:
        return 0

    signal.signal(signal.SIGTERM, handle_stop)
    signal.signal(signal.SIGINT, handle_stop)
    try:
        animate(sock_path)
    finally:
        handle.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

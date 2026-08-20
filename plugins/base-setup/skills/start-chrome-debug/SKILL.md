---
description: Start Chrome with remote debugging on port 9222 so the chrome-devtools MCP server can drive it (Linux, macOS, WSL)
version: "1.1"
---

# Start Chrome (remote debugging)

Launches a **visible** Chrome on port 9222 with a dedicated profile, so an MCP
browser server pointed at `http://127.0.0.1:9222` can attach to it.

Reuses an already-running debug Chrome instead of launching a second one — a
second launch silently fails to bind the port and leaves you with a browser that
has no debugging endpoint.

## Prerequisites

None of these ship with this plugin. Check them before running the launcher, and
offer to install whatever is missing.

**1. A browser.** `chrome-devtools-mcp` officially supports **Google Chrome** and
Chrome for Testing; Chromium builds may work but are not guaranteed, so the
launcher prefers Chrome and treats `chromium` / `chromium-browser` as a
best-effort fallback. When it finds nothing it prints the install command for the
detected platform. Ask the user before running any `sudo` install.

**2. `curl`.** Used to check the DevTools endpoint. The launcher fails fast if it
is missing, rather than reporting a misleading startup failure.

**3. An MCP server to drive the browser.** This repo registers none. If `/mcp`
lists no `chrome-devtools` server, add it at user scope:

```bash
claude mcp add -s user chrome-devtools \
  -- npx -y chrome-devtools-mcp@latest --browser-url=http://127.0.0.1:9222
```

That command needs **Node.js LTS and npm** on `PATH` (`npx` runs the server), and
the session must be restarted before the new tools appear. The Playwright MCP
server is an alternative, but it manages its own browser and does **not** need
this command.

## Instructions

Run this single block:

```bash
set -euo pipefail

PORT=9222
PROFILE="$HOME/.chrome-debug-profile"
# The same path as a regular expression, for pgrep/pkill: the dot must not match
# any character, and the path has to end at a space or line end, so a sibling
# profile such as .chrome-debug-profile-copy cannot match.
PROFILE_RE="$HOME/\.chrome-debug-profile( |$)"
VERSION_JSON="${TMPDIR:-/tmp}/chrome-debug-version.json"
LAUNCH_LOG="${TMPDIR:-/tmp}/chrome-debug-launch.log"
URL="http://127.0.0.1:$PORT/json/version"
TIMEOUT=10

if ! command -v curl >/dev/null 2>&1; then
  echo "curl is required to check the DevTools endpoint. Install curl, then re-run." >&2
  exit 1
fi

# Probe the DevTools endpoint rather than the port: this confirms remote
# debugging is actually enabled, and needs no lsof. The response body goes to a
# file, never to stdout - piping curl to stdout is blocked when the context-mode
# hook is installed.
probe() { curl -sf --max-time "${1:-2}" -o "$VERSION_JSON" "$URL"; }
report() { grep -o '"Browser": *"[^"]*"' "$VERSION_JSON" || echo "(no Browser field)"; }

# A single transient miss on a live endpoint would defeat the reuse check and
# relaunch needlessly. An idle Chrome can take several seconds to answer its
# first request, so the reuse check retries and allows a longer per-attempt
# timeout; a dead port still fails instantly with connection-refused, so this
# costs nothing in the common case. The wait loop below keeps the short
# single-shot probe, to bound its own deadline.
probe_settled() {
  for _ in 1 2 3; do
    probe 5 && return 0
    sleep 0.3
  done
  return 1
}

if probe_settled; then
  echo "Chrome already running with remote debugging on port $PORT"
  report
  # /json/version does not say which profile answered, so confirm the listener
  # is ours before letting the caller assume the dedicated profile.
  if ! pgrep -f -- "$PROFILE_RE" >/dev/null 2>&1; then
    echo "Warning: no process here is running $PROFILE, so the listener on port" >&2
    echo "$PORT is a different browser or profile and MCP tools will drive that" >&2
    echo "one. Stop it first if you wanted the dedicated debug profile." >&2
  fi
  exit 0
fi

# Chrome first (officially supported), then the chromium builds as a fallback,
# then the macOS app bundles.
CHROME=""
for name in google-chrome google-chrome-stable chromium chromium-browser; do
  if command -v "$name" >/dev/null 2>&1; then
    CHROME="$name"
    break
  fi
done
if [ -z "$CHROME" ]; then
  for app in \
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
    "$HOME/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
    "/Applications/Chromium.app/Contents/MacOS/Chromium"; do
    if [ -x "$app" ]; then
      CHROME="$app"
      break
    fi
  done
fi

if [ -z "$CHROME" ]; then
  echo "No Chrome or Chromium found on this machine." >&2
  case "$(uname -s)" in
    Darwin)
      echo "Install with: brew install --cask google-chrome" >&2
      ;;
    Linux)
      distro=unknown
      if [ -r /etc/os-release ]; then
        distro=$(grep -E '^(ID|ID_LIKE)=' /etc/os-release | tr -d '"' | cut -d= -f2 | tr '\n' ' ')
      fi
      case "$distro" in
        *debian*|*ubuntu*)
          cat >&2 <<'HINT'
Install Google Chrome (officially supported, unlike Chromium):
  wget -q -O - https://dl.google.com/linux/linux_signing_key.pub \
    | sudo gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg
  echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] \
http://dl.google.com/linux/chrome/deb/ stable main" \
    | sudo tee /etc/apt/sources.list.d/google-chrome.list
  sudo apt-get update && sudo apt-get install -y google-chrome-stable
HINT
          ;;
        *fedora*|*rhel*|*centos*)
          echo "Install Google Chrome from https://www.google.com/chrome (preferred)," >&2
          echo "or best effort: sudo dnf install -y chromium" >&2
          ;;
        *arch*)
          echo "Install Google Chrome from the AUR (preferred)," >&2
          echo "or best effort: sudo pacman -S --noconfirm chromium" >&2
          ;;
        *)
          echo "Install Google Chrome with this distro's package manager." >&2
          ;;
      esac
      if grep -qi microsoft /proc/version 2>/dev/null; then
        echo "WSL: install it inside the distro. Windows-side chrome.exe binds the" >&2
        echo "port on the Windows loopback, which WSL2 cannot reach at 127.0.0.1" >&2
        echo "unless mirrored networking is enabled." >&2
      fi
      ;;
    *)
      echo "Unsupported platform: $(uname -s). Use Linux, macOS, or WSL." >&2
      ;;
  esac
  exit 1
fi

# Keep Chrome's stderr: it is the only diagnostic when the endpoint never opens.
"$CHROME" \
  --remote-debugging-port="$PORT" \
  --user-data-dir="$PROFILE" \
  --no-first-run \
  --no-default-browser-check \
  > /dev/null 2> "$LAUNCH_LOG" &

# Wall-clock deadline. Counting iterations instead would allow roughly 50s once
# each probe's own timeout is included.
DEADLINE=$((SECONDS + TIMEOUT))
while [ "$SECONDS" -lt "$DEADLINE" ]; do
  sleep 0.5
  if probe; then
    echo "Chrome started with remote debugging on port $PORT"
    echo "Binary: $CHROME"
    report
    rm -f "$LAUNCH_LOG"
    exit 0
  fi
done

echo "Chrome did not expose the debugging endpoint on port $PORT within ${TIMEOUT}s." >&2
echo "Check whether port $PORT is held by another process, or whether" >&2
echo "$PROFILE is locked by a leftover Chrome." >&2
if [ -s "$LAUNCH_LOG" ]; then
  echo "--- Chrome stderr ---" >&2
  cat "$LAUNCH_LOG" >&2
fi
rm -f "$LAUNCH_LOG"
exit 1
```

Report the `Browser` value on success, and relay any warning about a foreign
listener. On failure, report the script's stderr — including the captured Chrome
stderr — verbatim; do not retry blindly, since the failure modes need different
fixes (missing binary vs. busy port vs. locked profile).

A failed launch can leave Chrome running: when the IPv4 port is already taken it
falls back to `ws://[::1]:9222`, which neither this check nor an MCP server
pointed at `127.0.0.1` can reach. Free the port, stop that Chrome with the
**Stopping** command below, then retry.

## Platform notes

| Platform | Binary used                                                                                           | Notes                                                                       |
| -------- | ----------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| Linux    | `google-chrome`, `google-chrome-stable`, then `chromium`, `chromium-browser` from `PATH`              | First match wins; the chromium builds are best effort only                  |
| macOS    | `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome` (also `~/Applications`, then Chromium) | The binary is invoked directly, not via `open`, so the flags actually apply |
| WSL      | The Linux binary installed inside the distro                                                          | Windows-side `chrome.exe` is not usable — see the WSL message in the script |
| Windows  | —                                                                                                     | Run it from WSL                                                             |

## Notes

- **Headed, not headless.** You will see a window. The MCP tools drive that
  window, so it must stay open.
- **Separate profile** (`~/.chrome-debug-profile`). Logins and cookies persist
  across restarts, and the user's main Chrome profile is never touched or
  unlocked. Same path works on Linux and macOS.
- **Chrome must be up before the MCP server needs it.** If the server started
  against a dead endpoint, restart the Claude Code session once Chrome is
  running.
- **Shell portability:** the block runs under zsh as well as bash, so it avoids
  bash-only constructs like `/dev/tcp`.

## Stopping

Targets only the debug instance, matching the profile path exactly — the user's
normal Chrome, and any similarly named profile, are left alone:

```bash
pkill -f -- "user-data-dir=$HOME/\.chrome-debug-profile( |$)"
```

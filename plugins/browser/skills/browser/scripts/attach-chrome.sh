#!/usr/bin/env bash
# Starts a locally installed Chrome with remote debugging on port 9222, using a
# dedicated profile, so a server pointed at http://127.0.0.1:9222 can attach.
# This is the --chrome path; the default browser flow is launch.sh.
#
#   attach-chrome.sh          start, or reuse one that is already listening
#   attach-chrome.sh --stop   stop only the dedicated debug instance
#
# Reuses a running debug Chrome rather than launching a second one: a second
# launch silently fails to bind the port and leaves a browser with no endpoint.
set -euo pipefail

# Git Bash on Windows has no pgrep/pkill and Chrome lives elsewhere, so this
# would fail halfway through. Say so up front instead.
case "$(uname -s)" in
  MINGW* | MSYS* | CYGWIN*)
    echo "--chrome is not supported on Windows yet. Use the default launcher (launch.sh)," >&2
    echo "which runs Playwright's Chrome for Testing instead of the installed Chrome." >&2
    exit 1
    ;;
esac

PORT=9222
PROFILE="$HOME/.chrome-debug-profile"
# The same path as a regular expression, for pgrep/pkill. $HOME can contain
# regex metacharacters, and an unescaped one would either miss the debug Chrome
# or match an unrelated command line, so every one of them is escaped. The
# trailing boundary is why a sibling .chrome-debug-profile-copy cannot match.
escape_ere() {
  local out=$1 ch
  out=${out//\\/\\\\}
  for ch in '.' '[' ']' '(' ')' '*' '+' '?' '{' '}' '|' '^' '$'; do
    out=${out//"$ch"/\\"$ch"}
  done
  printf '%s' "$out"
}
PROFILE_RE="$(escape_ere "$PROFILE")( |\$)"
# An owner-only directory per run. Fixed names under a shared TMPDIR can be
# pre-created as symlinks by another local user, who would then own whatever
# `curl -o` and the stderr redirect write once they open those paths.
RUN_DIR=$(mktemp -d "${TMPDIR:-/tmp}/chrome-debug.XXXXXX")
chmod 700 "$RUN_DIR"
VERSION_JSON="$RUN_DIR/version.json"
LAUNCH_LOG="$RUN_DIR/launch.log"
# Names exactly what it removes, rather than recursing over a variable path.
trap 'rm -f "$VERSION_JSON" "$LAUNCH_LOG"; rmdir "$RUN_DIR" 2>/dev/null || true' EXIT
URL="http://127.0.0.1:$PORT/json/version"
TIMEOUT=10

if [ "${1:-}" = "--stop" ]; then
  # Matches the profile path exactly, so the user's normal Chrome and any
  # similarly named profile are left alone.
  if pkill -f -- "user-data-dir=$PROFILE_RE"; then
    echo "Stopped the debug Chrome (other browsers untouched)."
  else
    status=$?
    # pkill uses 1 for no match and above that for its own failure. Folding the
    # two together would report a broken pkill as nothing having been running.
    if [ "$status" -gt 1 ]; then
      echo "pkill failed with status $status, so the debug Chrome may still be" >&2
      echo "running. Check it by hand before retrying." >&2
      exit "$status"
    fi
    echo "No debug Chrome was running; nothing to stop."
  fi
  exit 0
fi

if [ -n "${1:-}" ]; then
  echo "Unknown option: $1 (only --stop is accepted)" >&2
  exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "curl is required to check the DevTools endpoint. Install curl, then re-run." >&2
  exit 1
fi

# Probe the DevTools endpoint rather than the port: this confirms remote
# debugging is actually enabled, and needs no lsof. The response body goes to a
# file, never to stdout - piping curl to stdout is blocked when the context-mode
# hook is installed.
# A 2xx on its own proves nothing: any HTTP service can be holding this port,
# and a Chrome on the dedicated profile can be running while it does. So the
# response also has to carry the webSocketDebuggerUrl an attaching server needs.
probe() {
  curl -sf --max-time "${1:-2}" -o "$VERSION_JSON" "$URL" || return 1
  grep -q '"webSocketDebuggerUrl"[[:space:]]*:[[:space:]]*"ws' "$VERSION_JSON"
}
# Any HTTP answer at all, to tell a port held by something else from a free one.
port_answers() { curl -s -o /dev/null --max-time 2 "$URL"; }
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
  # /json/version does not say which profile answered. Exiting 0 here would let
  # the caller point an MCP server at a browser nobody identified, so a foreign
  # listener is a failure rather than a warning.
  if ! pgrep -f -- "$PROFILE_RE" >/dev/null 2>&1; then
    echo "Port $PORT is held by something that is not $PROFILE." >&2
    echo "Driving it would mean driving an unidentified browser, so stopping." >&2
    echo "Free the port, or drop --chrome and use the default launcher." >&2
    exit 1
  fi
  exit 0
fi

# Nothing answered as DevTools. If something is holding the port anyway, a
# launch would fail to bind and leave a browser with no endpoint, so name the
# real problem rather than starting one.
if port_answers; then
  echo "Port $PORT answers HTTP but not as a DevTools endpoint, so something" >&2
  echo "other than a debug Chrome is holding it. Stopping." >&2
  echo "Free the port, or drop --chrome and use the default launcher." >&2
  exit 1
fi

# Chrome before Chromium, and on macOS the app bundles before either: a
# `chromium` on PATH used to win over an installed Google Chrome, which
# contradicts preferring Chrome.
CHROME=""
if [ "$(uname -s)" = Darwin ]; then
  for app in \
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
    "$HOME/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"; do
    if [ -x "$app" ]; then
      CHROME="$app"
      break
    fi
  done
fi
[ -n "$CHROME" ] || for name in google-chrome google-chrome-stable chromium chromium-browser; do
  if command -v "$name" >/dev/null 2>&1; then
    CHROME="$name"
    break
  fi
done
# Last resort on macOS: a Chromium bundle, which is best effort only.
if [ -z "$CHROME" ] && [ -x "/Applications/Chromium.app/Contents/MacOS/Chromium" ]; then
  CHROME="/Applications/Chromium.app/Contents/MacOS/Chromium"
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
        *debian* | *ubuntu*)
          cat >&2 <<'HINT'
Install Google Chrome (chrome-devtools-mcp supports it; Chromium is best effort):
  wget -q -O - https://dl.google.com/linux/linux_signing_key.pub \
    | sudo gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg
  echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] \
http://dl.google.com/linux/chrome/deb/ stable main" \
    | sudo tee /etc/apt/sources.list.d/google-chrome.list
  sudo apt-get update && sudo apt-get install -y google-chrome-stable
HINT
          ;;
        *fedora* | *rhel* | *centos*)
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
  >/dev/null 2>"$LAUNCH_LOG" &

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

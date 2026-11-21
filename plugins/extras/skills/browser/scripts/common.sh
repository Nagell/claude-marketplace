# Sourced by the browser skill's scripts; not meant to be run on its own.
# shellcheck shell=bash

# One pinned CLI version for every call. Each CLI release expects its own
# chromium and ffmpeg builds, and unpinned `npm exec` runs whatever version is
# cached or newest. A newer CLI against older builds records nothing
# (`video-stop` fails with ENOENT on its temp .webm), and `install-browser` run
# by one version deletes builds that only another version uses.
# 0.1.23 expects chromium-1252 and ffmpeg-1013; recording was verified on it.
# Bump deliberately, then re-run preflight and a short test recording.
# shellcheck disable=SC2034  # read by the scripts that source this file
PW_CLI_PKG="@playwright/cli@0.1.23"

# The CLI reads this dotenv file itself when a session starts, so a login is
# filled by key name (`fill e3 BROWSER_ADMIN_PASSWORD`) and the values show up
# as <secret>NAME</secret> in its output instead of in the conversation.
BROWSER_CRED_FILE="${BROWSER_CREDENTIALS:-$HOME/.claude/browser-users.env}"
if [ -f "$BROWSER_CRED_FILE" ]; then
  export PLAYWRIGHT_MCP_SECRETS_FILE="$BROWSER_CRED_FILE"
fi

# Picks one build's directory out of `install-browser --dry-run` output on
# stdin. The dry run lists every build the pinned version wants (chromium,
# ffmpeg, the headless shell), so match on the build's own name - which also
# keeps `chromium-` from matching `chromium_headless_shell-`. Windows paths end
# in `\chromium-1252`, hence both separators.
install_dir_for() {
  sed -n 's/^ *Install location: *//p' | tr -d '\r' |
    grep -E "[/\\\\]$1-[0-9]+\$" | head -1 || true
}

# True when the build directory holds the marker a finished download leaves.
# The directory stays as the CLI reported it (a native C:\... path on Windows,
# which is what CHROME_BIN and the like want); only the check converts it, with
# cygpath where Git Bash provides it.
install_complete() {
  local dir=$1
  [ -n "$dir" ] || return 1
  if command -v cygpath >/dev/null 2>&1; then
    dir=$(cygpath -u -- "$dir")
  fi
  [ -f "$dir/INSTALLATION_COMPLETE" ]
}

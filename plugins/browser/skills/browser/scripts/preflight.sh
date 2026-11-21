#!/usr/bin/env bash
# Reports what the browser skill needs, what is present, and what is missing.
# Installs nothing, launches nothing, writes nothing. Output is JSON on stdout.
#
# Env overrides:
#   BROWSER_PROFILE_ROOT   where session profiles live
#   BROWSER_CREDENTIALS    path to the credential dotenv
#   BROWSER_SKIP_MCP=1     skip the `claude mcp list` probe
set -euo pipefail

# shellcheck source-path=SCRIPTDIR source=common.sh
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

PROFILE_ROOT="${BROWSER_PROFILE_ROOT:-$HOME/.cache/claude-browser}"
CRED_FILE="${BROWSER_CREDENTIALS:-$HOME/.claude/browser-users.env}"

# Renders a value safe to drop between JSON quotes. Captured tool output can
# carry newlines and colour codes, so those are folded rather than assumed away
# - a stray control character would make the whole document unparseable.
esc() {
  printf '%s' "${1:-}" |
    tr -d '\r' |
    tr -cd '\11\12\40-\176' |
    sed -e 's/\\/\\\\/g' -e 's/"/\\"/g' -e 's/\t/\\t/g' |
    awk 'BEGIN { ORS = "" } NR > 1 { print "\\n" } { print }'
}

# Renders an array of already-escaped strings as a JSON array.
arr() {
  local first=1 item
  printf '['
  for item in "$@"; do
    [ "$first" -eq 1 ] || printf ', '
    printf '"%s"' "$(esc "$item")"
    first=0
  done
  printf ']'
}

missing=()
advisories=()

# ---------------------------------------------------------------- platform ---
case "$(uname -s)" in
  Darwin) platform=darwin ;;
  Linux)
    if grep -qi microsoft /proc/version 2>/dev/null; then
      platform=wsl
    else
      platform=linux
    fi
    ;;
  # Git Bash, which is what Claude Code's Bash tool runs on Windows.
  MINGW* | MSYS* | CYGWIN*) platform=windows ;;
  *) platform=$(uname -s | tr '[:upper:]' '[:lower:]') ;;
esac

# ------------------------------------------------------------------- node ----
node_present=false
node_version=""
if command -v node >/dev/null 2>&1; then
  node_present=true
  node_version=$(node --version 2>/dev/null || true)
else
  missing+=("node")
fi

# npm, not npx: where Volta manages Node its npx shim forwards the arguments to
# npm and `npx @playwright/cli` dies with `Unknown command`.
npm_present=false
if command -v npm >/dev/null 2>&1; then
  npm_present=true
else
  missing+=("npm")
fi

# ----------------------------------------------------------- playwright cli --
# `exec --no` runs the package if present and refuses to fetch it if not, so a
# success here means the pinned CLI is usable without installing anything.
# Another version being cached does not count: its browser builds differ.
cli_available=false
cli_version=""
if [ "$npm_present" = true ]; then
  if probe_version=$(npm exec --no -- "$PW_CLI_PKG" --version 2>/dev/null | tail -1); then
    cli_available=true
    cli_version=$probe_version
  fi
fi

# Separately: has the user agreed to npm fetching what is missing? Recorded so
# the same question is not asked on every launch.
cli_consent=false
[ -f "$PROFILE_ROOT/.install-consent" ] && cli_consent=true

# Only missing if it is neither already usable nor cleared to be fetched.
if [ "$cli_available" = false ] && [ "$cli_consent" = false ]; then
  missing+=("playwright-cli")
fi

# ------------------------------------------------------------------ browser ---
# A definite answer, not a guess: `install-browser --dry-run` names the exact
# directories the pinned revision's builds belong in, and a finished download
# leaves an INSTALLATION_COMPLETE marker there. Globbing the cache could only
# say that some build existed, which once read as "nothing missing" while the
# one usable browser was absent.
#
# Only the CLI can answer, so without it the state is unknown (null), not
# absent: reporting "missing" there once had a user asked to download a browser
# that was already on disk.
browser_installed=null
browser_dir=""
ffmpeg_installed=null
ffmpeg_dir=""
dry_run_failed=false
if [ "$cli_available" = true ] &&
  ! dry_run=$(npm exec --no -- "$PW_CLI_PKG" install-browser --dry-run chromium 2>/dev/null); then
  dry_run_failed=true
fi
if [ "$cli_available" = true ] && [ "$dry_run_failed" = false ]; then
  browser_dir=$(install_dir_for chromium <<<"$dry_run")
  ffmpeg_dir=$(install_dir_for ffmpeg <<<"$dry_run")
  browser_installed=false
  install_complete "$browser_dir" && browser_installed=true
  # Playwright's own ffmpeg build writes video recordings; without it the
  # browser works but `video-stop` fails.
  ffmpeg_installed=false
  install_complete "$ffmpeg_dir" && ffmpeg_installed=true
fi

# Absent and unconsented is something to ask about; absent but already
# consented just needs --allow-install passing on the next launch.
case "$browser_installed" in
  false)
    if [ "$cli_consent" = false ]; then
      missing+=("browser")
    else
      advisories+=("browser is not installed; launch with --allow-install to fetch it")
    fi
    ;;
  null)
    if [ "$dry_run_failed" = true ]; then
      advisories+=("browser not checked: the pinned CLI's install-browser --dry-run failed; run it through pw.sh to see why")
    else
      advisories+=("browser not checked: that needs the pinned CLI first; launch --allow-install fetches the CLI and, only if absent, the browser")
    fi
    ;;
esac
# Not part of `missing`: only recording needs this build, so it must not hold
# up opening a browser. Fetching it is still a download, so it needs the yes.
if [ "$browser_installed" = true ] && [ "$ffmpeg_installed" = false ]; then
  if [ "$cli_consent" = false ]; then
    advisories+=("video recording unavailable: Playwright's ffmpeg build is missing; ask the user before fetching it with launch --allow-install")
  else
    advisories+=("video recording unavailable: Playwright's ffmpeg build is missing; launch with --allow-install to fetch it")
  fi
fi

# ------------------------------------------------------------ credentials ----
cred_present=false
cred_mode=""
logins=()
if [ -f "$CRED_FILE" ]; then
  cred_present=true
  cred_mode=$(stat -c '%a' "$CRED_FILE" 2>/dev/null || stat -f '%Lp' "$CRED_FILE" 2>/dev/null || true)
  while IFS= read -r login; do
    [ -n "$login" ] && logins+=("$login")
  done < <(sed -n 's/^BROWSER_\([A-Z0-9]*\)_EMAIL=.*/\1/p' "$CRED_FILE" |
    tr '[:upper:]' '[:lower:]' | sort -u)
  if [ -n "$cred_mode" ] && [ "$cred_mode" != "600" ]; then
    advisories+=("credential file is mode $cred_mode, expected 600")
  fi
fi

# ---------------------------------------------------------------- sessions ---
# `list --json` is the stable shape; the human-readable form is not. Anything
# else coming back means the CLI changed under us, which is worth saying out
# loud rather than silently reporting no sessions.
sessions_available=false
sessions_json='{ "browsers": [] }'
# `--no` again: listing sessions must never be the thing that triggers a
# download.
if [ "$cli_available" = true ]; then
  sessions_available=true
  raw_list=$(npm exec --no -- "$PW_CLI_PKG" list --json 2>/dev/null || true)
  case "$raw_list" in
    '{'*) sessions_json=$raw_list ;;
    *) advisories+=("could not read the session list from the Playwright CLI") ;;
  esac
fi

# --------------------------------------------------------------------- mcp ---
mcp_checked=false
mcp_playwright=false
mcp_playwright_sandbox=false
mcp_chrome_devtools=false
mcp_playwright_plugin=""
mcp_playwright_plugin_sandbox=false
if [ "${BROWSER_SKIP_MCP:-}" != "1" ] && command -v claude >/dev/null 2>&1; then
  if mcp_raw=$(claude mcp list 2>/dev/null); then
    mcp_checked=true
    # Per entry, not across the whole listing: a --sandbox belonging to some
    # other server used to be read as the Playwright one being correctly
    # registered. A plugin's server (`plugin:<name>:playwright:`) is reported
    # apart from the user's own, because `claude mcp remove` cannot change it.
    mcp_pw_line=$(printf '%s\n' "$mcp_raw" | grep -v '^plugin:' | grep -m1 -- playwright || true)
    mcp_pw_plugin_line=$(printf '%s\n' "$mcp_raw" |
      grep -m1 -E '^plugin:[^:]+:[^:]*playwright[^:]*:' || true)
    if [ -n "$mcp_pw_line" ]; then
      mcp_playwright=true
      case "$mcp_pw_line" in *"--sandbox"*) mcp_playwright_sandbox=true ;; esac
    fi
    if [ -n "$mcp_pw_plugin_line" ]; then
      mcp_playwright=true
      mcp_playwright_plugin=$(printf '%s' "$mcp_pw_plugin_line" | cut -d: -f2)
      case "$mcp_pw_plugin_line" in *"--sandbox"*) mcp_playwright_plugin_sandbox=true ;; esac
    fi
    case "$mcp_raw" in *chrome-devtools*) mcp_chrome_devtools=true ;; esac

    if [ -n "$mcp_pw_line" ] && [ "$mcp_playwright_sandbox" = false ]; then
      advisories+=("playwright MCP is registered without --sandbox; it will show a security warning bar")
    fi
    if [ -n "$mcp_playwright_plugin" ] && [ "$mcp_playwright_plugin_sandbox" = false ]; then
      advisories+=("playwright MCP from the $mcp_playwright_plugin plugin runs without --sandbox; claude mcp remove cannot change a plugin's server, the fix belongs in that plugin's .mcp.json")
    fi
    [ "$mcp_playwright" = true ] || advisories+=("playwright MCP is not registered")
    [ "$mcp_chrome_devtools" = true ] || advisories+=("chrome-devtools MCP is not registered")
  else
    advisories+=("claude mcp list failed, so the MCP servers were not checked")
  fi
fi

# ------------------------------------------------------------------ output ---
cat <<JSON
{
  "platform": "$(esc "$platform")",
  "profile_root": "$(esc "$PROFILE_ROOT")",
  "node": { "present": $node_present, "version": "$(esc "$node_version")" },
  "npm": { "present": $npm_present },
  "playwright_cli": {
    "package": "$(esc "$PW_CLI_PKG")",
    "available": $cli_available,
    "consent": $cli_consent,
    "version": "$(esc "$cli_version")"
  },
  "browser": {
    "installed": $browser_installed,
    "install_dir": "$(esc "$browser_dir")",
    "ffmpeg_installed": $ffmpeg_installed,
    "ffmpeg_dir": "$(esc "$ffmpeg_dir")"
  },
  "credentials": {
    "present": $cred_present,
    "path": "$(esc "$CRED_FILE")",
    "mode": "$(esc "$cred_mode")",
    "logins": $(arr ${logins+"${logins[@]}"})
  },
  "sessions": {
    "available": $sessions_available,
    "list": $sessions_json
  },
  "mcp": {
    "checked": $mcp_checked,
    "playwright": $mcp_playwright,
    "playwright_sandbox": $mcp_playwright_sandbox,
    "playwright_plugin": "$(esc "$mcp_playwright_plugin")",
    "playwright_plugin_sandbox": $mcp_playwright_plugin_sandbox,
    "chrome_devtools": $mcp_chrome_devtools
  },
  "missing": $(arr ${missing+"${missing[@]}"}),
  "advisories": $(arr ${advisories+"${advisories[@]}"})
}
JSON

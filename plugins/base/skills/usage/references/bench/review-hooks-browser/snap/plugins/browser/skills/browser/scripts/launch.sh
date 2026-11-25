#!/usr/bin/env bash
# Allocates and starts isolated Playwright CLI browser sessions, one profile
# each, so several can run side by side without fighting over one window.
#
#   launch.sh [--session NAME] [--count N] [--url URL] [--login NAME]
#             [--allow-install] [--yes-many]
#   launch.sh --list
#   launch.sh --stop NAME
#
# Env overrides:
#   BROWSER_PROFILE_ROOT   where session profiles live
#   BROWSER_WINDOW_ORIGIN  "x,y" of the first window, default "80,60"
set -euo pipefail

# shellcheck source-path=SCRIPTDIR source=common.sh
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

PROFILE_ROOT="${BROWSER_PROFILE_ROOT:-$HOME/.cache/claude-browser}"
# Coordinates are global, measured from the primary display's top-left, so a
# window meant for another monitor needs that monitor's offset in here.
WINDOW_ORIGIN="${BROWSER_WINDOW_ORIGIN:-80,60}"
# Above this many browsers the machine, not the script, becomes the limit, so
# the caller has to come back with an explicit go-ahead.
MANY=4

session=""
count=1
url=""
login=""
allow_install=false
yes_many=false
action=launch

die() {
  printf '%s\n' "$*" >&2
  exit 1
}

usage() {
  sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//'
}

# Accepts both `--flag value` and `--flag=value`; the second form is what the
# Playwright CLI itself uses, so callers reach for it out of habit.
while [ $# -gt 0 ]; do
  # Checked up front so a missing value is a message rather than a bare
  # non-zero exit from `shift 2` walking off the end of the list.
  case "$1" in
    --session | --count | --url | --login | --stop)
      [ $# -ge 2 ] || die "$1 needs a value."
      ;;
  esac

  case "$1" in
    --session)
      session=${2:-}
      shift 2
      ;;
    --session=*)
      session=${1#*=}
      shift
      ;;
    --count)
      count=${2:-}
      shift 2
      ;;
    --count=*)
      count=${1#*=}
      shift
      ;;
    --url)
      url=${2:-}
      shift 2
      ;;
    --url=*)
      url=${1#*=}
      shift
      ;;
    --login)
      login=${2:-}
      shift 2
      ;;
    --login=*)
      login=${1#*=}
      shift
      ;;
    --stop)
      action=stop
      session=${2:-}
      shift 2
      ;;
    --stop=*)
      action=stop
      session=${1#*=}
      shift
      ;;
    --list)
      action=list
      shift
      ;;
    --allow-install)
      allow_install=true
      shift
      ;;
    --yes-many)
      yes_many=true
      shift
      ;;
    -h | --help)
      usage
      exit 0
      ;;
    *) die "Unknown option: $1 (try --help)" ;;
  esac
done

command -v npm >/dev/null 2>&1 || die "npm not found. Run scripts/preflight.sh first."

# Fetching tooling is an install and needs a yes, but asking on every launch
# would be noise: the first yes is recorded and answers for later runs.
CONSENT_MARKER="$PROFILE_ROOT/.install-consent"
if [ "$allow_install" = true ]; then
  mkdir -p "$PROFILE_ROOT"
  : >"$CONSENT_MARKER"
fi

# `exec --yes` fetches if needed; `exec --no` refuses to. npm and not npx:
# where Volta manages Node its npx shim forwards the arguments to npm, so a bare
# `npx @playwright/cli` fails with `Unknown command: "@playwright/cli"`.
if [ -f "$CONSENT_MARKER" ]; then
  RUNNER_ARGS=(exec --yes --)
else
  RUNNER_ARGS=(exec --no --)
fi

# The engine has to be pinned. Unpinned, and with `--browser=chrome`, the CLI
# launches the browser the user browses with, which a managed device's Chrome
# policy may lock down (RemoteDebuggingAllowed=0 makes the run fail outright).
# `chromium` selects Playwright's own Chrome for Testing build and has no
# `--browser` value, which is why the env var is the handle. scripts/pw.sh does
# the same for every call after launch, minus the fetching.
pw() {
  PLAYWRIGHT_MCP_BROWSER=chromium npm "${RUNNER_ARGS[@]}" "$PW_CLI_PKG" "$@"
}

pw_available() {
  pw --version >/dev/null 2>&1
}

# Session names end up in paths and in a regex below, so keep them to a
# character set that is safe in both.
sanitize() {
  printf '%s' "$1" | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9-' '-' |
    sed -e 's/-\{2,\}/-/g' -e 's/^-//' -e 's/-$//'
}

# Matching on the bare name would make `alpha` look alive whenever `alpha-1`
# is, so require a non-name character on each side. Reading `list --json` keeps
# this working if the human-readable listing is ever reformatted.
session_running() {
  pw list --json 2>/dev/null | grep -Eq "(^|[^A-Za-z0-9_-])$1([^A-Za-z0-9_-]|\$)"
}

case "$action" in
  list)
    pw_available || die "Playwright CLI is not installed yet. Re-run with --allow-install."
    printf 'Running sessions:\n'
    pw list --json || true
    if [ -d "$PROFILE_ROOT" ]; then
      printf '\nProfiles on disk (%s):\n' "$PROFILE_ROOT"
      ls -1 "$PROFILE_ROOT" 2>/dev/null || true
    fi
    exit 0
    ;;

  stop)
    [ -n "$session" ] || die "--stop needs a session name."
    session=$(sanitize "$session")
    # There is deliberately no stop-everything: another agent's browser is not
    # this caller's to close.
    case "$session" in
      all | "*") die "Refusing to stop everything. Name one session." ;;
    esac
    pw_available || die "Playwright CLI is not installed yet, so nothing is running."
    pw -s="$session" close
    printf 'Stopped session: %s (any other session is untouched)\n' "$session"
    exit 0
    ;;
esac

# ------------------------------------------------------------------ launch ---
case "$count" in
  '' | *[!0-9]*) die "--count must be a whole number, got: $count" ;;
esac
[ "$count" -ge 1 ] || die "--count must be at least 1."

# Negative values are legitimate: a monitor left of or above the primary one.
[[ "$WINDOW_ORIGIN" =~ ^(-?[0-9]+),(-?[0-9]+)$ ]] ||
  die "BROWSER_WINDOW_ORIGIN must be \"x,y\" in whole pixels, got: $WINDOW_ORIGIN"
origin_x=${BASH_REMATCH[1]}
origin_y=${BASH_REMATCH[2]}

if [ "$count" -gt "$MANY" ] && [ "$yes_many" = false ]; then
  die "$count browsers is a lot - each is a real browser, roughly 400 MB of RAM
apiece. Confirm with the user, then re-run with --yes-many."
fi

if ! pw_available; then
  if [ "$allow_install" = true ]; then
    die "Could not fetch the Playwright CLI through npm. Check the network and npm output."
  fi
  die "Playwright CLI is not installed. Ask the user first, then re-run with --allow-install."
fi

# Only under an explicit yes - this is the download worth asking about.
#
# Neither the exit status nor the output can be trusted: the CLI exits 0 whether
# or not it installed anything, and prints its "install your dependencies first"
# box on success too. So verify against the locations it reports, where a
# finished download leaves an INSTALLATION_COMPLETE marker, and keep the output
# - a silent no-op here resurfaces as a launch crash. The same install fetches
# Playwright's ffmpeg build. Only video recording needs it, so a failed ffmpeg
# download warns rather than costing the user their browser.
build_installed() {
  install_complete "$(install_dir_for "$1" <<<"$2")"
}

if [ "$allow_install" = true ]; then
  pw install-browser chromium || true

  dry_run=$(pw install-browser --dry-run chromium 2>/dev/null || true)
  if ! build_installed chromium "$dry_run"; then
    chromium_dir=$(install_dir_for chromium <<<"$dry_run")
    die "Playwright's chromium build is still not installed.
The CLI reports its install location as: ${chromium_dir:-<could not determine>}
Run this to see what it says:
  npm exec --yes -- $PW_CLI_PKG install-browser chromium"
  fi
  if ! build_installed ffmpeg "$dry_run"; then
    printf '%s\n' "Warning: Playwright's ffmpeg build did not install, so video recording will not
work. The browser itself is fine. To retry: launch.sh --allow-install" >&2
  fi
fi

if [ -n "$session" ]; then
  base=$(sanitize "$session")
else
  # The basename alone is not unique: /work/team-a/app and /work/team-b/app
  # would share a name, and session_running would then hand the second caller
  # the first one's browser and profile. A digest of the full path separates
  # them while keeping the name recognisable.
  base=$(sanitize "$(basename "$PWD")-$(printf '%s' "$PWD" | cksum | cut -c1-6)")
fi
[ -n "$base" ] || base=browser

running_count() {
  pw list --json 2>/dev/null |
    node -e 'let s="";process.stdin.on("data",d=>s+=d).on("end",()=>{let n=0;try{n=JSON.parse(s).browsers.length}catch{}process.stdout.write(String(n))})'
}

# The window size is set at launch rather than corrected afterwards, so the
# window never jumps. A null viewport lets the page follow the window instead
# of being pinned inside it. Each slot cascades by 40px so several sessions
# stay distinguishable.
write_config() {
  local config=$1 slot=$2
  cat >"$config" <<JSON
{
  "browser": {
    "launchOptions": {
      "args": ["--window-size=1440,1000", "--window-position=$((origin_x + slot * 40)),$((origin_y + slot * 40))"]
    },
    "contextOptions": { "viewport": null }
  }
}
JSON
}

start_one() {
  local name=$1 slot=$2 profile
  profile="$PROFILE_ROOT/$name"

  if session_running "$name"; then
    printf 'Reused session: %s (already running, profile %s)\n' "$name" "$profile"
    return 0
  fi

  # The profile is created without asking: it is what keeps a login alive
  # across restarts, and an empty directory costs nothing if unused.
  mkdir -p "$profile"
  chmod 700 "$profile"

  write_config "$profile/cli.config.json" "$slot"

  local open_args=(open)
  [ -n "$url" ] && open_args+=("$url")
  open_args+=(--headed "--profile=$profile" "--config=$profile/cli.config.json")

  pw -s="$name" "${open_args[@]}"

  cat >"$profile/session.json" <<JSON
{
  "session": "$name",
  "profile": "$profile",
  "marker": "$(printf '%s' "$name" | tr '[:lower:]' '[:upper:]')",
  "login": "$login",
  "created": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
JSON

  printf 'Started session: %s\n' "$name"
  printf '  profile: %s\n' "$profile"
  printf '  marker:  %s   (prefix records you create with this)\n' \
    "$(printf '%s' "$name" | tr '[:lower:]' '[:upper:]')"
  [ -n "$login" ] && printf '  login:   %s\n' "$login"
  printf '  stop:    %s --stop %s\n' "$0" "$name"
}

first_slot=$(running_count)
if [ "$count" -eq 1 ]; then
  start_one "$base" "$first_slot"
else
  i=1
  while [ "$i" -le "$count" ]; do
    start_one "$base-$i" $((first_slot + i - 1))
    i=$((i + 1))
  done
  printf '\n%s browsers running. They share the application, not their windows -\n' "$count"
  printf 'read references/parallel.md before they touch anything shared.\n'
fi

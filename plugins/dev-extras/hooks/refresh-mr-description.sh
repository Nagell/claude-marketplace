#!/usr/bin/env bash
# Regenerate the marker-delimited block of a GitHub PR or GitLab MR description after a push.
#
#   refresh-mr-description.sh hook                 PostToolUse entry: JSON on stdin, detaches
#   refresh-mr-description.sh run [--adopt] [--force] [--dry-run] [--wait-remote]
#
# Only the text between these two lines is ever replaced:
#   <!-- mr-desc:start sha=<pushed HEAD> hash=<git blob hash of the block body> -->
#   <!-- mr-desc:end -->
# A description without markers is left alone unless --adopt is given, which puts the markers
# below a leading `## ` title and the signed author's note quoted under it. If the block no
# longer matches its recorded hash, a human edited it and the refresh is skipped unless
# --force is given.
#
# The forge is read from the remote URL (a URL containing "github" means GitHub, anything else
# GitLab); set MR_DESC_FORGE=github|gitlab to override, e.g. for GitHub Enterprise.
#
# Requires: git, jq, claude (logged in), and gh or glab (authenticated).
set -euo pipefail

readonly START_TAG='<!-- mr-desc:start'
readonly END_TAG='<!-- mr-desc:end -->'
readonly MODEL="${MR_DESC_MODEL:-haiku}"
readonly MAX_DIFF_CHARS="${MR_DESC_MAX_DIFF_CHARS:-120000}"
readonly MAX_BLOCK_CHARS=20000
readonly REMOTE_POLL_TRIES=20
readonly REMOTE_POLL_SECONDS=3
readonly STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/mr-desc-refresh"
SCRIPT_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"
readonly SCRIPT_PATH
readonly STYLE_FILE="${SCRIPT_PATH%/*}/../skills/pr-descriptions/SKILL.md"

log() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >&2; }
die() {
  log "error: $*"
  exit 1
}

usage() {
  sed -n '2,14p' "$SCRIPT_PATH" | sed 's/^# \{0,1\}//'
}

require_tools() {
  local tool
  for tool in "$@"; do
    command -v "$tool" >/dev/null || die "'$tool' is not on PATH"
  done
}

# The hook's `if` rules are best-effort (`$VAR` commands and `git * push*` false positives
# get through), so this is the real check, and for `-C` it returns <dir> rather than the
# hook's cwd. The hook's cwd is where the command started, so a `cd <dir>` before the push
# names the pushed repo.
push_repo_dir() { # push_repo_dir <command> <cwd>: prints the pushed repo dir, or fails
  local cmd="$1" cwd="$2" dir
  local lead='(^|[;&|(][[:space:]]*|^[A-Za-z_][A-Za-z0-9_]*=[^[:space:]]*[[:space:]]+)'
  local tail='[[:space:]]+push([[:space:]]|$)'
  local c_opt="${lead}git[[:space:]]+-C[[:space:]]+([^[:space:];&|]+)${tail}"
  local cd_first="(^|[;&(][[:space:]]*)cd[[:space:]]+([^[:space:];&|]+)"
  cd_first+="[[:space:]]*(&&|;).*git${tail}"
  local plain="${lead}git${tail}"
  if [[ "$cmd" =~ $c_opt || "$cmd" =~ $cd_first ]]; then
    dir="${BASH_REMATCH[2]}"
    [[ "$dir" == \~ || "$dir" == \~/* ]] && dir="$HOME${dir:1}"
    [[ "$dir" == /* ]] || dir="$cwd/$dir"
    printf '%s\n' "$dir"
  elif [[ "$cmd" =~ $plain ]]; then
    printf '%s\n' "$cwd"
  else
    return 1
  fi
}

hook_entry() {
  # The child `claude -p` loads this plugin too; never let it recurse.
  [[ -z "${MR_DESC_REFRESH:-}" ]] || return 0
  local input cmd cwd repo_dir
  input=$(cat)
  cmd=$(jq -r '.tool_input.command // empty' <<<"$input") || die "hook input is not JSON"
  cwd=$(jq -r '.cwd // empty' <<<"$input")
  repo_dir=$(push_repo_dir "$cmd" "$cwd") || return 0
  [[ -d "$repo_dir" ]] || die "pushed repo dir does not exist: $repo_dir"
  mkdir -p "$STATE_DIR"
  # Detached so the refresh survives the session ending; async hooks are killed at
  # teardown in -p mode. setsid is missing on macOS, where nohup alone has to do.
  local runner=(nohup)
  command -v setsid >/dev/null && runner=(setsid nohup)
  (
    cd "$repo_dir"
    "${runner[@]}" "$SCRIPT_PATH" run --wait-remote >>"$STATE_DIR/refresh.log" 2>&1 </dev/null &
  )
}

blob_hash() { printf '%s' "$1" | git hash-object --stdin; }

# The web editors may send CRLF, and edits around the block can shift blank lines;
# neither should count as a human edit of the block.
normalize() {
  local s="${1//$'\r'/}"
  s="${s#"${s%%[![:space:]]*}"}"
  s="${s%"${s##*[![:space:]]}"}"
  printf '%s' "$s"
}

count_of() { # count_of <haystack> <needle>
  local rest="${1//"$2"/}"
  echo $(((${#1} - ${#rest}) / ${#2}))
}

# Sets DESC_PRE, DESC_BLOCK, DESC_POST, MARK_SHA, MARK_HASH. Returns 1 when there are no
# markers; dies when they are present but malformed.
split_description() {
  local desc="$1" starts ends
  starts=$(count_of "$desc" "$START_TAG")
  ends=$(count_of "$desc" "$END_TAG")
  ((starts == 0 && ends == 0)) && return 1
  ((starts == 1 && ends == 1)) || die "expected one start and one end marker, found $starts/$ends"
  DESC_PRE="${desc%%"$START_TAG"*}"
  local rest="${desc#*"$START_TAG"}"
  [[ "$rest" == *"$END_TAG"* ]] || die "end marker comes before the start marker"
  local attrs="${rest%%-->*}"
  local attr_re='^[[:space:]]*sha=([0-9a-f]{40})[[:space:]]+hash=([0-9a-f]{40})[[:space:]]*$'
  [[ "$attrs" =~ $attr_re ]] || die "malformed start marker: $START_TAG$attrs-->"
  MARK_SHA="${BASH_REMATCH[1]}"
  MARK_HASH="${BASH_REMATCH[2]}"
  rest="${rest#*-->}"
  DESC_BLOCK="$(normalize "${rest%%"$END_TAG"*}")"
  DESC_POST="${rest#*"$END_TAG"}"
}

# For --adopt. Sets DESC_PRE to a leading `## ` title line plus the author's note quote
# directly under it (recognised by its `> — name` signature), and DESC_REST to the rest.
split_head() { # split_head <description>
  local nl=$'\n'
  local line="[^$nl]*($nl|\$)"
  local head="^([[:space:]]*## $line([[:space:]]*(>$line)*>[[:space:]]*— $line)?)"
  DESC_PRE="" DESC_REST="$1"
  [[ "$1" =~ $head ]] || return 0
  DESC_PRE="${BASH_REMATCH[1]}"
  DESC_REST="${1:${#DESC_PRE}}"
  # A blank line before the start marker, so it cannot read as part of the quote.
  [[ "$DESC_PRE" == *"$nl" ]] || DESC_PRE+="$nl"
  DESC_PRE+="$nl"
}

ensure_pushed() { # ensure_pushed <remote> <branch> <head> <wait: 0|1>
  local remote="$1" branch="$2" head="$3" wait="$4" tries=1 remote_sha
  ((wait)) && tries=$REMOTE_POLL_TRIES
  while ((tries-- > 0)); do
    remote_sha=$(git ls-remote "$remote" "refs/heads/$branch" | cut -f1)
    [[ "$remote_sha" == "$head" ]] && return 0
    ((tries > 0)) && sleep "$REMOTE_POLL_SECONDS"
  done
  die "$remote/$branch is at '${remote_sha:-missing}', not HEAD $head; push first"
}

detect_forge() { # detect_forge <remote>
  if [[ -n "${MR_DESC_FORGE:-}" ]]; then
    printf '%s\n' "$MR_DESC_FORGE"
    return
  fi
  case "$(git remote get-url "$1")" in
  *github*) echo github ;;
  *) echo gitlab ;;
  esac
}

# Sets PR_ID (the API handle), PR_REF (`#12` or `!12`) and PR_TARGET for the open PR/MR
# whose source branch is <branch>. Returns 1 when there is none.
find_pr() { # find_pr <branch>
  local pr
  if [[ "$FORGE" == github ]]; then
    pr=$(gh pr list --head "$1" --state open --limit 1 --json number,baseRefName | jq -c '.[0]')
    [[ "$pr" != null ]] || return 1
    PR_ID=$(jq -r .number <<<"$pr")
    PR_REF="#$PR_ID"
    PR_TARGET=$(jq -r .baseRefName <<<"$pr")
  else
    pr=$(glab api "projects/:id/merge_requests?state=opened&source_branch=$1" | jq -c '.[0]')
    [[ "$pr" != null ]] || return 1
    PR_ID="$(jq -r .project_id <<<"$pr")/merge_requests/$(jq -r .iid <<<"$pr")"
    PR_REF="!$(jq -r .iid <<<"$pr")"
    PR_TARGET=$(jq -r .target_branch <<<"$pr")
  fi
}

fetch_description() {
  if [[ "$FORGE" == github ]]; then
    gh pr view "$PR_ID" --json body --jq '.body // ""'
  else
    glab api "projects/$PR_ID" | jq -r '.description // ""'
  fi
}

put_description() { # put_description <file>
  if [[ "$FORGE" == github ]]; then
    gh pr edit "$PR_ID" --body-file "$1" >/dev/null
  else
    glab api --method PUT "projects/$PR_ID" --field "description=@$1" >/dev/null
  fi
}

build_input() { # build_input <current block> <remote> <target branch> <head> <out file>
  local block="$1" remote="$2" target="$3" head="$4" out="$5" base diff truncated=no
  git fetch --quiet "$remote" "$target"
  base=$(git merge-base FETCH_HEAD "$head")
  diff=$(git diff "$base" "$head")
  if ((${#diff} > MAX_DIFF_CHARS)); then
    diff="${diff:0:MAX_DIFF_CHARS}"
    truncated=yes
  fi
  {
    printf '<current_block>\n%s\n</current_block>\n\n' "${block:-(empty: write it from scratch)}"
    printf '<commits>\n%s\n</commits>\n\n' "$(git log --reverse --format='- %s' "$base..$head")"
    printf '<diff_stat>\n%s\n</diff_stat>\n\n' "$(git diff --stat "$base" "$head")"
    printf '<diff truncated="%s">\n%s\n</diff>\n' "$truncated" "$diff"
  } >"$out"
}

write_system_prompt() { # write_system_prompt <out file>
  [[ -f "$STYLE_FILE" ]] || die "house style file missing: $STYLE_FILE"
  {
    cat <<'EOF'
You maintain one block of a pull request / merge request description. You get the current block,
the branch's commits, and its diff against the target branch. Return the block rewritten
so it describes the diff as it is now.

- Keep wording that is still true. Change only what the diff contradicts or adds, and
  drop claims about changes that are no longer in the diff.
- Never make the block longer than the diff needs. Add no callout, section or bullet the
  current block does not have unless the diff adds something a reviewer must know.
- Say what changed for the reader, not how the code does it: no internals such as
  process handling, state paths or implementation details, in bullets or the file map.
- Keep links, ticket references and alerts from the current block that still apply.
  Never invent tickets, links, test results or numbers that are not in the input.
- If the diff is marked truncated, describe only what you can see and do not guess.
- Never add a `## ` title heading or an author's note quote: those sit above the block.
- Output only the block's Markdown. No preamble, no code fence around it, and never the
  text "<!-- mr-desc:", not even quoted or in code; call them "the markers".

Follow this house style:

EOF
    # The skill's YAML frontmatter is for the skill loader, not the model.
    awk 'NR == 1 && /^---$/ { fm = 1; next } fm && /^---$/ { fm = 0; next } !fm' "$STYLE_FILE"
  } >"$1"
}

# Prints the new block on stdout. Runs a tool-less, settings-less child session: it is a
# pure text transform, and MR_DESC_REFRESH stops this plugin's hook from recursing.
generate_block() { # generate_block <input file> <system prompt file> <work dir>
  local input="$1" system="$2" work="$3" block
  # Thinking off: with it, Haiku took ~70 s instead of ~6 s on a 50k-char input.
  MR_DESC_REFRESH=1 MAX_THINKING_TOKENS=0 claude -p --model "$MODEL" --tools "" \
    --setting-sources "" --strict-mcp-config --disable-slash-commands \
    --no-session-persistence --max-budget-usd 0.25 --output-format json \
    --system-prompt-file "$system" "Rewrite the MR description block from the input on stdin." \
    <"$input" >"$work/claude.json" || die "claude -p failed: $(head -c 500 "$work/claude.json")"
  block=$(jq -r 'if .is_error then error(.result) else .result end' "$work/claude.json") ||
    die "claude returned an error (see $work/claude.json)"
  log "model=$MODEL cost_usd=$(jq -r '.total_cost_usd // "?"' "$work/claude.json")"
  # Guard against a fenced answer despite the instruction; the fence would render literally.
  block="$(normalize "$block")"
  if [[ "$block" == '```'* && "$block" == *'```' ]]; then
    block="${block#*$'\n'}"
    block="$(normalize "${block%'```'}")"
  fi
  # Haiku sometimes echoes the marker lines it saw in the input around its answer.
  block="$(normalize "$(sed -E '/^[[:space:]]*<!-- mr-desc:(start|end)[^>]*-->[[:space:]]*$/d' \
    <<<"$block")")"
  [[ -n "$block" ]] || die "model returned an empty block"
  [[ "$block" != *"<!-- mr-desc:"* ]] || die "model output contains marker text; refusing to write"
  ((${#block} <= MAX_BLOCK_CHARS)) || die "model output is ${#block} chars (max $MAX_BLOCK_CHARS)"
  printf '%s\n' "$block"
}

# Re-fetches right before the PUT so text others changed during the model run (CodeRabbit,
# a reviewer) outside the block is kept, and aborts if the block itself moved.
write_block() { # write_block <old desc> <new block> <head> <adopt 0|1> <work dir>
  local old="$1" block="$2" head="$3" adopt="$4" work="$5" fresh hash
  fresh=$(fetch_description)
  if ((adopt)); then
    [[ "$fresh" == "$old" ]] || die "description changed during the refresh; run again"
    split_head "$fresh"
    DESC_POST=""
  else
    split_description "$old"
    local old_hash
    old_hash=$(blob_hash "$DESC_BLOCK")
    split_description "$fresh" || die "markers disappeared during the refresh; run again"
    [[ "$(blob_hash "$DESC_BLOCK")" == "$old_hash" ]] ||
      die "the block was edited during the refresh; run again"
  fi
  mkdir -p "$STATE_DIR/backups"
  local backup
  backup="$STATE_DIR/backups/$(basename "$PWD")-$FORGE-${PR_REF:1}-$(date -u +%Y%m%dT%H%M%SZ).md"
  printf '%s' "$fresh" >"$backup"
  hash=$(blob_hash "$block")
  printf '%s%s sha=%s hash=%s -->\n%s\n%s%s' "$DESC_PRE" "$START_TAG" "$head" "$hash" \
    "$block" "$END_TAG" "$DESC_POST" >"$work/description.md"
  put_description "$work/description.md"
  split_description "$(fetch_description)" ||
    die "write did not stick: live description has no markers (backup: $backup)"
  [[ "$MARK_SHA" == "$head" && "$MARK_HASH" == "$hash" ]] ||
    die "write did not stick: live markers are sha=$MARK_SHA hash=$MARK_HASH (backup: $backup)"
  log "refreshed $PR_REF to $head (previous description: $backup)"
}

run_refresh() {
  local adopt=0 force=0 dry_run=0 wait_remote=0
  while (($#)); do
    case "$1" in
    --adopt) adopt=1 ;;
    --force) force=1 ;;
    --dry-run) dry_run=1 ;;
    --wait-remote) wait_remote=1 ;;
    *) die "unknown option: $1" ;;
    esac
    shift
  done
  # A detached run's only output is the log, so name the failing line there.
  set -E
  trap 'log "error: line $LINENO: $BASH_COMMAND"' ERR
  require_tools git jq claude
  local branch head remote desc block
  git rev-parse --git-dir >/dev/null || die "not a git repository: $PWD"
  branch=$(git symbolic-ref --quiet --short HEAD) || die "detached HEAD in $PWD"
  head=$(git rev-parse HEAD)
  remote=$(git config --get "branch.$branch.remote" || echo origin)
  ensure_pushed "$remote" "$branch" "$head" "$wait_remote"
  FORGE=$(detect_forge "$remote")
  if [[ "$FORGE" == github ]]; then require_tools gh; else require_tools glab; fi
  if ! find_pr "$branch"; then
    log "no open PR/MR for $branch; nothing to refresh"
    return 0
  fi
  desc=$(fetch_description)
  if split_description "$desc"; then
    ((adopt)) && die "$PR_REF already has markers; use --force to refresh past the edit guard"
    if [[ "$(blob_hash "$DESC_BLOCK")" != "$MARK_HASH" ]] && ((! force)); then
      log "$PR_REF: block was edited by hand since the last refresh; skipped (use --force)"
      return 0
    fi
    if [[ "$MARK_SHA" == "$head" ]] && ((! force)); then
      log "$PR_REF: block already describes $head; skipped"
      return 0
    fi
    block="$DESC_BLOCK"
  elif ((adopt)); then
    split_head "$desc"
    block="$(normalize "$DESC_REST")"
  else
    log "$PR_REF: description has no mr-desc markers; left alone (adopt with --adopt)"
    return 0
  fi
  local work
  work=$(mktemp -d)
  # shellcheck disable=SC2064 # expand now: $work is local and gone by the time EXIT fires
  trap "rm -rf '$work'" EXIT
  build_input "$block" "$remote" "$PR_TARGET" "$head" "$work/input.md"
  write_system_prompt "$work/system.md"
  block=$(generate_block "$work/input.md" "$work/system.md" "$work")
  if ((dry_run)); then
    printf '%s\n' "$block"
    return 0
  fi
  write_block "$desc" "$block" "$head" "$adopt" "$work"
}

main() {
  case "${1:-}" in
  hook) hook_entry ;;
  run)
    shift
    run_refresh "$@"
    ;;
  -h | --help) usage ;;
  *)
    usage >&2
    exit 2
    ;;
  esac
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  main "$@"
fi

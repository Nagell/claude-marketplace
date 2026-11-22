#!/bin/bash

# Safety Guards - PreToolUse hook for Bash commands
# Blocks dangerous operations and warns on risky patterns
# Compatible with Windows (Git Bash, WSL) and Unix systems
#
# Exit codes:
# 0 - Allow command to proceed (use JSON systemMessage for warnings)
# 2 - Block command execution (stderr shown to model)

set -euo pipefail

# Read JSON input from stdin (Claude Code passes tool input this way)
INPUT=$(cat)

# Extract the command from JSON input
# Use sed for compatibility (grep -oP is not available on all systems)
# Pattern handles JSON-escaped quotes (\") by matching [^"\\] OR escape sequences (\\.)
COMMAND=$(echo "$INPUT" | sed -n 's/.*"command"\s*:\s*"\(\([^"\\]*\(\\.[^"\\]*\)*\)\)".*/\1/p' 2>/dev/null | sed 's/\\"/"/g;s/\\\\/\\/g' | head -1)

# If we couldn't extract command, allow (fail open for non-Bash tools)
if [ -z "$COMMAND" ]; then
  exit 0
fi

# Collect warnings
WARNINGS=""
PUSH_NOTICE=""

add_warning() {
  if [ -n "$WARNINGS" ]; then
    WARNINGS="$WARNINGS | $1"
  else
    WARNINGS="$1"
  fi
}

# ============================================
# BLOCK: Hardcoded secrets in commands
# ============================================

SECRET_PATTERNS="(API_KEY|SECRET|TOKEN|PASSWORD|PRIVATE_KEY|ACCESS_KEY|SECRET_KEY|AUTH_TOKEN)=['\"]?[a-zA-Z0-9_\-]{16,}"

if echo "$COMMAND" | grep -qE "$SECRET_PATTERNS"; then
  echo "BLOCKED: Potential hardcoded secret detected. Use environment variables instead." >&2
  exit 2
fi

# ============================================
# Command text for the force push check and the push token gate below
# ============================================

# Prints $COMMAND with line continuations joined and heredoc bodies dropped (text
# in a heredoc is data, not a command). With `drop_heredocs keep`, bodies of
# unquoted heredocs (<<EOF) are kept, because bash still runs $(...) and backticks
# inside them; quoted ones (<<'EOF', the usual commit message form) are dropped.
drop_heredocs() {
  printf '%s\n' "$COMMAND" | sed 's/\\n/\n/g' |
    awk -v keep="${1:-}" '
      term != "" { l = $0; sub(/^\t+/, "", l); if (l == term) term = ""; else if (keep != "" && !quoted) print; next }
      { while (/\\$/ && (getline nx) > 0) $0 = substr($0, 1, length($0) - 1) nx }
      match($0, /(^|[^<])<<-?[ \t]*["'\'']?[A-Za-z0-9_]+/) {
        term = substr($0, RSTART, RLENGTH); quoted = (term ~ /["'\'']/)
        sub(/^[^<]*<<-?[ \t]*["'\'']?/, "", term)
      }
      { print }'
}
HEREDOC_FREE=$(drop_heredocs)

# CMD_PARTS holds one simple command per line: heredoc bodies dropped, split on
# ; && || | & ( ) ` and newlines, quote characters removed (the words inside
# quotes stay, so rm -rf "$HOME" is still seen). Each rule below looks at one
# part at a time, so a path in another part (cd /home/me/x && rm -rf "$tmp")
# never triggers it.
CMD_PARTS=$(printf '%s\n' "$HEREDOC_FREE" | sed -E 's/(&&|\|\||[;|&()`])/\n/g' | tr -d "\"'")

# Words that may come before the real command in a part.
PREFIX_RE='^(sudo|command|exec|nohup|time|rtk|xargs|eval|env|-[[:alnum:]-]+|[A-Za-z_][A-Za-z0-9_]*=.*|(ba|z|da)?sh)$'

# Prints the words of a part from the real command on (prefixes dropped).
command_words() {
  local w seen=""
  set -f
  for w in $1; do
    if [ -z "$seen" ] && [[ $w =~ $PREFIX_RE ]]; then continue; fi
    seen=1
    printf '%s\n' "$w"
  done
  set +f
}

# ============================================
# BLOCK: rm -rf on home or root
# Strict on purpose: any path under a home folder counts, not only the folder.
# ============================================

is_danger_path() {
  case $1 in
    "~" | "~/"* | '$HOME' | '$HOME/'* | '${HOME}' | '${HOME}/'*) return 0 ;;
    /home/* | /Users/* | /root | /root/*) return 0 ;;
  esac
  # / itself, a top-level folder (/usr, /etc) or a top-level wildcard (/*, /us*)
  [[ $1 =~ ^/[^/]*/?$ || $1 =~ ^/[^/]*\* ]] && return 0
  return 1
}

while IFS= read -r PART; do
  mapfile -t WORDS < <(command_words "$PART")
  [ "${#WORDS[@]}" -gt 0 ] || continue
  [[ ${WORDS[0]} == rm || ${WORDS[0]} == */rm ]] || continue
  RECURSIVE="" FORCE="" TARGETS=()
  for W in "${WORDS[@]:1}"; do
    case $W in
      --recursive) RECURSIVE=1 ;;
      --force) FORCE=1 ;;
      --*) ;;
      -*)
        [[ $W == *[rR]* ]] && RECURSIVE=1
        [[ $W == *f* ]] && FORCE=1
        ;;
      *) TARGETS+=("$W") ;;
    esac
  done
  [ -n "$RECURSIVE" ] && [ -n "$FORCE" ] || continue
  for W in "${TARGETS[@]}"; do
    if is_danger_path "$W"; then
      echo "BLOCKED: rm -rf on a home or root path ($W). Command: $COMMAND" >&2
      exit 2
    fi
  done
done <<<"$CMD_PARTS"

# ============================================
# BLOCK: writing a .env file via shell
# Reads stay allowed; .env.example, .sample, .template and .dist are never blocked.
# ============================================

is_env_file() {
  local b=${1##*/}
  [[ $b =~ ^\.env(\.[A-Za-z0-9_-]+)?$ ]] || return 1
  [[ $b =~ ^\.env\.(example|sample|template|dist)$ ]] && return 1
  return 0
}

block_env() {
  echo "BLOCKED: writing $1 via shell. Ask the user to edit it, or use proper secrets management." >&2
  exit 2
}

while IFS= read -r PART; do
  # Redirections anywhere in the part: > file, >> file, >file
  while read -r TARGET; do
    if [ -n "$TARGET" ] && is_env_file "$TARGET"; then block_env "$TARGET"; fi
  done < <(printf '%s\n' "$PART" | { grep -oE '>{1,2}[[:space:]]*[^[:space:]<>]+' || true; } | sed -E 's/^>{1,2}[[:space:]]*//')

  mapfile -t WORDS < <(command_words "$PART")
  [ "${#WORDS[@]}" -gt 0 ] || continue
  ARGS=()
  for W in "${WORDS[@]:1}"; do [[ $W == -* ]] || ARGS+=("$W"); done
  [ "${#ARGS[@]}" -gt 0 ] || continue
  case ${WORDS[0]##*/} in
    tee | truncate)
      for W in "${ARGS[@]}"; do if is_env_file "$W"; then block_env "$W"; fi; done ;;
    cp | mv | install | ln)
      if [ "${#ARGS[@]}" -gt 1 ] && is_env_file "${ARGS[-1]}"; then block_env "${ARGS[-1]}"; fi ;;
    sed | perl)
      if [[ " ${WORDS[*]:1} " =~ [[:space:]]-[[:alnum:]]*i ]]; then
        for W in "${ARGS[@]}"; do if is_env_file "$W"; then block_env "$W"; fi; done
      fi ;;
  esac
done <<<"$CMD_PARTS"

# PUSH_TEXT holds one shell command per line, from two sources:
# 1. The command itself with quoted strings stripped, so a commit message that
#    mentions `git push` is not a push. Split on ; && || | & newlines and on
#    ( ) ` so subshells and unquoted $(...) are seen.
# 2. Code that runs even when it sits inside quotes: $(...), backticks and the
#    string after sh -c, bash -lc, eval, --exec or -x. Here the quotes are kept
#    as separators instead of stripped, so nothing inside them is hidden.
# Matching is unanchored (`env X=1 git push`, `then git push`, `rtk git push`
# all count). When unsure this errs towards a match: a false match costs one
# token prompt, a missed one lets an unapproved push through.
TOP_TEXT=$(printf '%s\n' "$HEREDOC_FREE" |
  tr '\n' '\036' | sed "s/\"[^\"]*\"//g; s/'[^']*'//g" | tr '\036' '\n' |
  sed -E 's/(&&|\|\||[;|&()`])/\n/g')
NESTED_RE='\$\([^)]*|`[^`]*`|(^|[[:space:]])(-[[:alnum:]]*c|--exec|-x|eval)[[:space:]]+("[^"]*"|'\''[^'\'']*'\'')'
NESTED_TEXT=$(drop_heredocs keep | tr '\n' '\036' | { grep -oE "$NESTED_RE" || true; } |
  tr '\036"'\''`()' '\n' | sed -E 's/(&&|\|\||[;|&])/\n/g')
PUSH_TEXT=$(printf '%s\n%s\n' "$TOP_TEXT" "$NESTED_TEXT")
PUSH_RE='(^|[[:space:]/])git([[:space:]]+-{1,2}[^[:space:]]+([[:space:]]+[^[:space:]-][^[:space:]]*)?)*[[:space:]]+push([^[:alnum:]_-]|$)'

# ============================================
# BLOCK: Unsafe git force push
# Runs before the push token gate below, so a blocked force push keeps the token.
# ============================================

# Each `git [opts] push` is checked argument by argument: -f, --force[=...],
# short-flag clusters with f (-uf) and +refspecs block; --force-with-lease and
# --force-if-includes pass.
# Limitation: a quoted argument (`git push origin "+main"`) is not seen.
PUSH_FOUND=""
while IFS= read -r SEGMENT; do
  [[ $SEGMENT =~ $PUSH_RE ]] || continue
  PUSH_FOUND=1
  read -ra PUSH_ARGS <<<"${SEGMENT#*"${BASH_REMATCH[0]}"}"
  for ARG in "${PUSH_ARGS[@]}"; do
    case $ARG in
      --force-with-lease* | --force-if-includes) continue ;;
    esac
    if [[ $ARG == --force || $ARG == --force=* || $ARG == +* || $ARG =~ ^-[[:alpha:]]*f[[:alpha:]]*$ ]]; then
      echo "BLOCKED: force push ($ARG) without --force-with-lease. Use --force-with-lease instead." >&2
      exit 2
    fi
  done
done <<<"$PUSH_TEXT"

# ============================================
# CONFIRM: git push requires user approval
# Works in all permission modes including bypass
# ============================================

if [ -n "$PUSH_FOUND" ]; then
  # The hook runs in the session's directory, which is often not the repo being pushed,
  # so resolve the repo from the command: the `git -C <dir> ... push`, else a leading `cd <dir>`.
  PUSH_DIR=""
  C_RE="git[[:space:]]+-C[[:space:]]+(\"[^\"]+\"|'[^']+'|[^[:space:];&|]+)([[:space:]]+[^[:space:];&|]+)*[[:space:]]+push([[:space:];&|)]|$)"
  CD_RE="^[[:space:]]*cd[[:space:]]+(\"[^\"]+\"|'[^']+'|[^[:space:];&|]+)"
  if [[ $HEREDOC_FREE =~ $C_RE ]]; then
    PUSH_DIR=${BASH_REMATCH[1]}
  elif [[ $HEREDOC_FREE =~ $CD_RE ]]; then
    PUSH_DIR=${BASH_REMATCH[1]}
  fi
  PUSH_DIR=${PUSH_DIR#[\"\']}
  PUSH_DIR=${PUSH_DIR%[\"\']}
  PUSH_DIR=${PUSH_DIR/#\~/$HOME}
  GIT_ROOT=$(git -C "${PUSH_DIR:-.}" rev-parse --show-toplevel 2>/dev/null || echo "$HOME")
  TOKEN_FILE="$GIT_ROOT/.claude-push-token"
  if [ -f "$TOKEN_FILE" ]; then
    rm -f "$TOKEN_FILE"
    PUSH_NOTICE="Push token consumed; this hook auto-removed $TOKEN_FILE. Do not delete it yourself."
  else
    # After the user's explicit yes for this push, the agent creates the token in the
    # repo root itself, in its own Bash call, then pushes in a second call. (The hook
    # runs before the command, so `touch ... && git push` in one call is denied.)
    printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"Git push requires explicit user confirmation. Ask the user NOW and wait for their reply. Only after their explicit yes for this push, create the token in the repo root in its own Bash call: `touch %s`, then rerun the original git push command in a second call."}}' "$TOKEN_FILE"
    exit 0
  fi
fi

# ============================================
# WARN: Dangerous git operations (not blocked)
# ============================================

if echo "$COMMAND" | grep -qE 'git\s+reset\s+--hard'; then
  add_warning "git reset --hard will destroy uncommitted changes"
fi

if echo "$COMMAND" | grep -qE 'git\s+clean\s+-[a-zA-Z]*f'; then
  add_warning "git clean will permanently delete untracked files"
fi

# ============================================
# WARN: Production keywords
# ============================================

PROD_KEYWORDS="(production|prod\.|prod-|\.prod|PROD_|--production|@production)"

if echo "$COMMAND" | grep -qiE "$PROD_KEYWORDS"; then
  add_warning "Command contains production-related keywords - verify this is intentional"
fi

# ============================================
# WARN: Database operations
# ============================================

if echo "$COMMAND" | grep -qiE '(DROP\s+TABLE|DROP\s+DATABASE|TRUNCATE|DELETE\s+FROM)'; then
  add_warning "Potentially destructive database operation detected"
fi

# ============================================
# Output warnings as JSON systemMessage
# ============================================

if [ -n "$WARNINGS" ] && [ -n "$PUSH_NOTICE" ]; then
  echo "{\"systemMessage\": \"SAFETY WARNING: $WARNINGS\", \"hookSpecificOutput\": {\"hookEventName\": \"PreToolUse\", \"additionalContext\": \"$PUSH_NOTICE\"}}"
elif [ -n "$WARNINGS" ]; then
  echo "{\"systemMessage\": \"SAFETY WARNING: $WARNINGS\"}"
elif [ -n "$PUSH_NOTICE" ]; then
  echo "{\"hookSpecificOutput\": {\"hookEventName\": \"PreToolUse\", \"additionalContext\": \"$PUSH_NOTICE\"}}"
fi

exit 0

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
# BLOCK: Destructive filesystem operations
# ============================================

# Block rm -rf targeting home or root directories
if echo "$COMMAND" | grep -qE 'rm\s+(-[a-zA-Z]*r[a-zA-Z]*f|.*-rf)\s'; then
  # Check for dangerous paths: ~, $HOME, /Users/username, /home/username, /
  if echo "$COMMAND" | grep -qE '(~[/\s]|\$HOME|/Users/[^/\s]+[/\s]|/home/[^/\s]+[/\s]|^\s*/\s*$|\s+/\s+)'; then
    echo "BLOCKED: Destructive rm command targeting home or root directory. Command: $COMMAND" >&2
    exit 2
  fi

  # Block rm -rf with wildcards at dangerous levels
  if echo "$COMMAND" | grep -qE 'rm\s+-rf\s+/[^/]*\*'; then
    echo "BLOCKED: rm -rf with wildcard at root level" >&2
    exit 2
  fi
fi

# ============================================
# BLOCK: Hardcoded secrets in commands
# ============================================

SECRET_PATTERNS="(API_KEY|SECRET|TOKEN|PASSWORD|PRIVATE_KEY|ACCESS_KEY|SECRET_KEY|AUTH_TOKEN)=['\"]?[a-zA-Z0-9_\-]{16,}"

if echo "$COMMAND" | grep -qE "$SECRET_PATTERNS"; then
  echo "BLOCKED: Potential hardcoded secret detected. Use environment variables instead." >&2
  exit 2
fi

# ============================================
# BLOCK: .env file modifications via shell
# ============================================

if echo "$COMMAND" | grep -qE '(echo|cat|printf|>>|>)\s+.*\.env'; then
  echo "BLOCKED: Attempting to modify .env file via shell. Use proper secrets management." >&2
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

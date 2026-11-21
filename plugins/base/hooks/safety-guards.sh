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
# BLOCK: Unsafe git force push
# Runs before the push token gate below, so a blocked force push keeps the token.
# ============================================

# Command text for this check: heredoc bodies dropped, quoted strings stripped,
# one shell command per line. Each `git [opts] push` is checked argument by
# argument: -f, --force[=...], short-flag clusters with f (-uf) and +refspecs
# block; --force-with-lease and --force-if-includes pass.
# Limitation: a quoted argument (`git push origin "+main"`) is not seen.
FORCE_TEXT=$(printf '%s\n' "$COMMAND" | sed 's/\\n/\n/g' |
  awk 'term != "" { l = $0; sub(/^\t+/, "", l); if (l == term) term = ""; next }
    match($0, /(^|[^<])<<-?[ \t]*["'\'']?[A-Za-z0-9_]+/) {
      term = substr($0, RSTART, RLENGTH); sub(/^[^<]*<<-?[ \t]*["'\'']?/, "", term)
    }
    { print }' |
  tr '\n' '\036' | sed "s/\"[^\"]*\"//g; s/'[^']*'//g" | tr '\036' '\n' |
  sed -E 's/(&&|\|\||[;|&])/\n/g')
PUSH_RE='(^|[[:space:]/])git([[:space:]]+-{1,2}[^[:space:]]+([[:space:]]+[^[:space:]-][^[:space:]]*)?)*[[:space:]]+push([[:space:]]|$)'
while IFS= read -r SEGMENT; do
  [[ $SEGMENT =~ $PUSH_RE ]] || continue
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
done <<<"$FORCE_TEXT"

# ============================================
# CONFIRM: git push requires user approval
# Works in all permission modes including bypass
# ============================================

# Truncate at first heredoc marker (<<) to avoid matching "git push" inside heredoc content,
# then strip remaining quoted strings
BEFORE_HEREDOC=$(echo "$COMMAND" | awk '{if(/<</) {sub(/<<.*/,""); print; exit} print}')
CMD_STRIPPED=$(echo "$BEFORE_HEREDOC" | sed 's/"[^"]*"//g' | sed "s/'[^']*'//g")
if echo "$CMD_STRIPPED" | grep -qE '(^|\s*;\s*|\s*&&\s*|\s*\|\|\s*)(rtk\s+(proxy\s+)?)?git(\s+-{1,2}[^[:space:]]+(\s+[^[:space:]-][^[:space:]]*)?)*\s+push([^[:alnum:]_-]|$)'; then
  # The hook runs in the session's directory, which is often not the repo being pushed,
  # so resolve the repo from the command: `git -C <dir>`, else a leading `cd <dir>`.
  PUSH_DIR=""
  C_RE="git[[:space:]]+-C[[:space:]]+(\"[^\"]+\"|'[^']+'|[^[:space:];&|]+)"
  CD_RE="^[[:space:]]*cd[[:space:]]+(\"[^\"]+\"|'[^']+'|[^[:space:];&|]+)"
  if [[ $BEFORE_HEREDOC =~ $C_RE ]]; then
    PUSH_DIR=${BASH_REMATCH[1]}
  elif [[ $BEFORE_HEREDOC =~ $CD_RE ]]; then
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

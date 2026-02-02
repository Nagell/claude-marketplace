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
# ============================================

if echo "$COMMAND" | grep -qE 'git\s+push\s+.*--force[^-]'; then
  if ! echo "$COMMAND" | grep -qE 'force-with-lease'; then
    echo "BLOCKED: git push --force without --force-with-lease. Use --force-with-lease for safety." >&2
    exit 2
  fi
fi

if echo "$COMMAND" | grep -qE 'git\s+push\s+(-f|.*\s-f)(\s|$)'; then
  echo "BLOCKED: git push -f detected. Use --force-with-lease instead." >&2
  exit 2
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
# WARN: Leaving projects directory
# ============================================

if echo "$COMMAND" | grep -qE 'cd\s+(/|~|\.\.|C:\\Users)' && ! echo "$COMMAND" | grep -qiE 'Projects'; then
  add_warning "You may be leaving the Projects directory context"
fi

# ============================================
# Output warnings as JSON systemMessage
# ============================================

if [ -n "$WARNINGS" ]; then
  echo "{\"systemMessage\": \"SAFETY WARNING: $WARNINGS\"}"
fi

exit 0

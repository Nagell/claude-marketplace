#!/bin/bash

# Post-Edit Format Hook
# Auto-fix lint, format, and style errors after Edit/Write operations
# Compatible with Windows (Git Bash, WSL) and Unix systems

# Read JSON input from stdin
INPUT=$(cat)

# Extract file_path from tool input JSON
# Use sed for compatibility (grep -oP is not available on all systems)
FILE=$(echo "$INPUT" | sed -n 's/.*"file_path"\s*:\s*"\([^"]*\)".*/\1/p' 2>/dev/null | head -1)

# Exit if no file
if [ -z "$FILE" ]; then
  exit 0
fi

# Convert Windows paths to Unix paths if needed (for WSL/Git Bash compatibility)
if [[ "$FILE" =~ ^[A-Za-z]: ]]; then
  # Windows path detected, convert to Unix-style if in Git Bash
  if [ -n "$MSYSTEM" ]; then
    FILE=$(echo "$FILE" | sed 's|\\|/|g' | sed 's|^\([A-Za-z]\):|/\L\1|')
  fi
fi

# Exit if file doesn't exist
if [ ! -f "$FILE" ]; then
  exit 0
fi

# Get file extension
EXT="${FILE##*.}"

# Get project root (where package.json or similar exists)
PROJECT_ROOT=$(pwd)

# ============================================
# Detect available formatters/linters
# ============================================

HAS_OXFMT=false
HAS_PRETTIER=false
HAS_ESLINT=false
HAS_STYLELINT=false
HAS_RUFF=false
HAS_BLACK=false

# Node.js project detection
if [ -f "$PROJECT_ROOT/package.json" ]; then
  if command -v npx &>/dev/null; then
    # Check if oxfmt is available (preferred over prettier)
    if [ -f "$PROJECT_ROOT/.oxfmtrc.json" ] && npx oxfmt --version &>/dev/null 2>&1; then
      HAS_OXFMT=true
    fi
    # Check if prettier is available (fallback when oxfmt is not configured)
    if ! $HAS_OXFMT && npx prettier --version &>/dev/null 2>&1; then
      HAS_PRETTIER=true
    fi
    # Check if eslint is available
    if npx eslint --version &>/dev/null 2>&1; then
      HAS_ESLINT=true
    fi
    # Check if stylelint is available
    if npx stylelint --version &>/dev/null 2>&1; then
      HAS_STYLELINT=true
    fi
  fi
fi

# Python project detection
if [ -f "$PROJECT_ROOT/pyproject.toml" ] || [ -f "$PROJECT_ROOT/setup.py" ]; then
  if command -v ruff &>/dev/null; then
    HAS_RUFF=true
  fi
  if command -v black &>/dev/null; then
    HAS_BLACK=true
  fi
fi

# ============================================
# Apply formatters based on file type
# ============================================

case "$EXT" in
  # JavaScript/TypeScript/Vue/JSX/TSX
  js|jsx|ts|tsx|vue|svelte)
    if $HAS_OXFMT; then
      npx oxfmt --write "$FILE" 2>/dev/null || true
    elif $HAS_PRETTIER; then
      npx prettier --write "$FILE" 2>/dev/null || true
    fi
    if $HAS_ESLINT; then
      npx eslint --fix "$FILE" 2>/dev/null || true
    fi
    if $HAS_STYLELINT && [[ "$EXT" == "vue" || "$EXT" == "svelte" ]]; then
      npx stylelint --fix "$FILE" 2>/dev/null || true
    fi
    ;;

  # CSS/SCSS/Less
  css|scss|less|sass)
    if $HAS_OXFMT; then
      npx oxfmt --write "$FILE" 2>/dev/null || true
    elif $HAS_PRETTIER; then
      npx prettier --write "$FILE" 2>/dev/null || true
    fi
    if $HAS_STYLELINT; then
      npx stylelint --fix "$FILE" 2>/dev/null || true
    fi
    ;;

  # JSON/YAML/Markdown
  json|yaml|yml|md)
    if $HAS_OXFMT; then
      npx oxfmt --write "$FILE" 2>/dev/null || true
    elif $HAS_PRETTIER; then
      npx prettier --write "$FILE" 2>/dev/null || true
    fi
    ;;

  # HTML
  html|htm)
    if $HAS_OXFMT; then
      npx oxfmt --write "$FILE" 2>/dev/null || true
    elif $HAS_PRETTIER; then
      npx prettier --write "$FILE" 2>/dev/null || true
    fi
    ;;

  # Python
  py)
    if $HAS_RUFF; then
      ruff check --fix "$FILE" 2>/dev/null || true
      ruff format "$FILE" 2>/dev/null || true
    elif $HAS_BLACK; then
      black "$FILE" 2>/dev/null || true
    fi
    ;;

  # GraphQL
  graphql|gql)
    if $HAS_OXFMT; then
      npx oxfmt --write "$FILE" 2>/dev/null || true
    elif $HAS_PRETTIER; then
      npx prettier --write "$FILE" 2>/dev/null || true
    fi
    ;;

  *)
  
    # Unknown file type, try oxfmt or prettier if available
    if $HAS_OXFMT; then
      npx oxfmt --write "$FILE" 2>/dev/null || true
    elif $HAS_PRETTIER; then
      npx prettier --write "$FILE" 2>/dev/null || true
    fi
    ;;
esac

exit 0

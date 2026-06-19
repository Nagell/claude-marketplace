#!/usr/bin/env bash
# Runs after every Bash tool use. Returns immediately on non-commits.
set -euo pipefail

# PostToolUse hooks receive a JSON payload on stdin (with tool_input.command).
# Some Claude Code versions also expose the command via $CLAUDE_TOOL_INPUT.
# We only need substring matching to detect commits, so read the raw payload as
# a string and fall back to the env var. (Note: rtk/context-mode may rewrite the
# command to `rtk git commit ...` — the "git commit" substring still matches.)
INPUT="$(cat 2>/dev/null || true)"
INPUT="${INPUT:-${CLAUDE_TOOL_INPUT:-}}"

case "$INPUT" in
  *"git commit"*) ;;
  *) exit 0 ;;
esac

case "$INPUT" in
  *"--dry-run"*|*"--amend"*) exit 0 ;;
esac

# Inject text into the agent. A PostToolUse hook only reaches the model via JSON
# `hookSpecificOutput.additionalContext` — plain stdout is NOT surfaced. python3
# is already required by this plugin's skill scripts, so we use it to emit safe
# JSON (handles quotes/newlines/unicode in the message).
emit() {
  python3 -c 'import json,sys; print(json.dumps({"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":sys.argv[1]}}))' "$1"
}

PROFILE="$HOME/coding-tutor-tutorials/learner_profile.md"

if [ ! -f "$PROFILE" ]; then
  emit "[coding-tutor] No learner profile at ${PROFILE}. Run /teach-me once to trigger coding-tutor's onboarding interview. The hook will start nudging once the profile exists."
  exit 0
fi

FILES=$(git log -1 --name-only --format='' 2>/dev/null | sed '/^$/d' | head -15 | tr '\n' ' ')

emit "[coding-tutor] User just committed. Files: ${FILES}

Read ${PROFILE}. If the user has added calibration rules (per-domain bars, frequency targets), apply them. If the profile only contains coding-tutor's onboarding answers, use general judgement:
- Skip routine refactors, bugfixes, copy tweaks, tests-only commits, config-only commits.
- Offer /teach-me with a topic anchored in the actual change when the change introduces a new pattern, library, or architectural idea.
- Max one /teach-me offer per session. If the user declines, drop the topic for this session.

If you offer, stay silent about this nudge. If you decide not to offer, also stay silent — do not mention the nudge fired."

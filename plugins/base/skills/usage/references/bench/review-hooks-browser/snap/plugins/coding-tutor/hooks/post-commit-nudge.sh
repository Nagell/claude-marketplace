#!/usr/bin/env bash
# Runs after every Bash tool use. Returns immediately on non-commits.
set -euo pipefail

# PostToolUse payload arrives on stdin (tool_input.command); some versions also
# expose it via $CLAUDE_TOOL_INPUT. We only need substring matching to detect a
# commit. (rtk/context-mode may rewrite `git commit` → `rtk git commit`; the
# "git commit" substring still matches.)
INPUT="$(cat 2>/dev/null || true)"
INPUT="${INPUT:-${CLAUDE_TOOL_INPUT:-}}"

case "$INPUT" in
  *"git commit"*) ;;
  *) exit 0 ;;
esac

# Skip dry-runs and amends. An amend would otherwise re-fire right after the
# original commit and nudge the same work twice.
case "$INPUT" in
  *"--dry-run"*|*"--amend"*) exit 0 ;;
esac

TUT_DIR="$HOME/coding-tutor-tutorials"

# Resolve the repo this commit happened in. Not a git repo → nothing to nudge.
GIT_DIR="$(git rev-parse --absolute-git-dir 2>/dev/null)" || exit 0

# Don't nudge on commits made inside the tutorials repo itself (e.g. the
# /sync-tutorials command commits + pushes that repo).
[ "$(git rev-parse --show-toplevel 2>/dev/null)" = "$TUT_DIR" ] && exit 0

# Only fire when HEAD actually moved. PostToolUse fires even on failed / no-op
# commits, and `git show/log HEAD` reads HEAD regardless — without this gate a
# rejected commit would report the PREVIOUS commit's files (phantom-file bug).
# The marker lives in THIS repo's .git, so the check is per-repo and can't be
# confused by a HEAD recorded while committing in a different project.
MARKER="$GIT_DIR/.coding-tutor-last-head"
HEAD_NOW="$(git rev-parse HEAD 2>/dev/null || echo none)"
[ "$HEAD_NOW" = "none" ] && exit 0
[ "$HEAD_NOW" = "$(cat "$MARKER" 2>/dev/null || true)" ] && exit 0
printf '%s\n' "$HEAD_NOW" > "$MARKER" 2>/dev/null || true

# Inject text into the agent. A PostToolUse hook only reaches the model via JSON
# `hookSpecificOutput.additionalContext` — plain stdout is silently dropped.
# python3 is already required by this plugin's skill scripts.
emit() {
  python3 -c 'import json,sys; print(json.dumps({"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":sys.argv[1]}}))' "$1"
}

PROFILE="$TUT_DIR/learner_profile.md"

if [ ! -f "$PROFILE" ]; then
  emit "[coding-tutor] No learner profile at ${PROFILE}. Run /teach-me once to trigger coding-tutor's onboarding interview. The hook will start nudging once the profile exists."
  exit 0
fi

# Richer signal than filenames so the eligibility triggers below are decidable:
# the commit subject + diffstat, and any newly added import/require lines (which
# distinguish "new library" from "copy tweak").
DIFFSTAT=$(git show HEAD --stat --format='%s' 2>/dev/null | head -20 || true)
NEW_IMPORTS=$(git show HEAD --format='' 2>/dev/null | grep -E '^\+\s*(import|from|require|use )' | head -20 || true)

MSG=$(cat <<EOF
[coding-tutor] User just committed.

Change summary (subject + diffstat):
${DIFFSTAT}

Newly added import/require lines (if any):
${NEW_IMPORTS:-(none)}

Read ${PROFILE} for calibration, then act in this order:

1. ELIGIBILITY (decide silently, first). If the change is clearly trivial — formatting/lint-only, lockfile/dependency bumps, generated files, pure renames/moves, or reverts — do NOTHING: no popup, no message. Otherwise continue. There is no per-session cap, but do not re-offer a concept already drilled or Skipped earlier in this session.

2. RAISE A POPUP IMMEDIATELY, before preparing anything (no file copies, no tutorial, no reading beyond the profile). Use the AskUserQuestion tool, with a header naming the topic you infer from the change summary / new imports above, and these options:
   - "Train — write a slice yourself" (the default / recommended)
   - "Teach — explain <topic>"
   - "Skip"
   Infer the topic from the diffstat and new imports above — you do NOT need to read files first.

3. ONLY AFTER the choice, run the matching flow from the coding-tutor skill:
   - Train → Training Mode (the live drill). Before a fresh drill you may resurface an overdue past drill instead — the skill's "Training Mode" section explains how (train_priority.py).
   - Teach → create/deliver the tutorial, then offer its closing drill.
   - Skip (or a dismissed/blank popup) → stop, no re-prompt on this commit.
EOF
)

emit "$MSG"

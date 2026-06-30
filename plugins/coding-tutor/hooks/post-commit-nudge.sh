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

Read ${PROFILE} and apply its calibration rules. Default bias: OFFER a tutorial unless the change is clearly trivial.
- Eligible (offer), including small fixes: a composable/hook, an unfamiliar API/library import, async, reactivity, regex, type-level code, a directory not yet tutored, or a recurring pattern.
- Skip ONLY: formatting/lint-only, lockfile/dependency bumps, generated files, pure renames/moves, reverts.
- Don't repeat topics already covered in the profile's tutorials; prefer a fresh angle.
- Offer up to N per session (default 3; honor any frequency target in the profile). "Declined" applies to that topic only, not the whole session.
- Always end with a one-line trailer: "↳ tutorial: <topic> — offered" or "↳ tutorial: <topic> — skipped(<reason>)".
EOF
)

emit "$MSG"

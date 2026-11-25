# Review brief: snapshot of a Claude Code plugin marketplace

The code under review is a snapshot of files from a Claude Code plugin marketplace. It is plain files with no git history:

`<snap>/`

What the parts do:
- `plugins/*/hooks/`: Claude Code hooks. Each `hooks.json` registers a script for an event (PreToolUse, PostToolUse, ...). The script reads the event JSON on stdin; its exit code and stdout decide what happens (exit 2 blocks the tool call; JSON output with `permissionDecision` deny/allow, or `additionalContext`). `safety-guards.sh` guards Bash commands, including a push gate: a `git push` is allowed only when a one-time `.claude-push-token` file exists in the repo root, and the hook consumes it. `post-edit-format.sh` formats files after edits. `refresh-mr-description.sh` rewrites a marked block of an MR/PR description after a push. `post-commit-nudge.sh` nudges after a commit.
- `plugins/browser/`: a skill that starts and drives a Playwright-managed browser for Claude, including parallel isolated sessions, stored logins (credentials) and attaching to an installed Chrome. `scripts/*.sh` do the work; `SKILL.md` and `references/*.md` tell Claude how to use them.

## Rules
- Read-only. Do not modify the snapshot. Do not read anything under `<session scratchpad>/` except `exp2/snap/` and this brief. Do not look at any git repository for these files.
- You may run the scripts against stubs and test input in a throwaway directory under /tmp (e.g. pipe hook JSON into a hook, put fake `git`/`npx`/`curl` on PATH). Never run a real `git push`, never create `.claude-push-token` in a real repo, never start a real browser, never touch real credentials. If a Bash command of yours contains push text, a real guard hook may check it; put such tests in a script file and run it by path.
- Measure what you can; mark the rest as derived and name what would settle it.

## Report
Write to the path in your prompt, then reply with only that path.
1. Coverage ledger: one row per file in your scope with a verdict; then the edges you followed.
2. Findings, worst first. Each: id (your prefix + number), severity (critical/high/medium/low, by consequence for a user of the plugin), one file:line, the mechanism and its trigger in 2-3 sentences, confidence (measured or derived).
3. A short "checked and found sound" list.
No style nits padding the list; "nothing found" is a valid answer.

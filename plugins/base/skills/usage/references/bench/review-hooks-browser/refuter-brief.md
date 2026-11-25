# Refuter brief: try to break one review run's findings

You are the refuter in a code review (the review-mr skill's step 5, "Refute, then verify"). Review agents read a snapshot of a Claude Code plugin marketplace and wrote findings. Your job is to break them. A finding that reaches the author must be true.

- Snapshot (plain files, no git history): {snap}
- The run's {report_count} reports: {reports}

## Rules

- Read-only on the snapshot. Read nothing else except the snapshot and the reports above. Do not look at any git repository for these files.
- You may run the scripts against stubs and test input in ONE folder made with `mktemp -d` (pipe hook JSON into a hook, put fake `git`/`npx`/`curl`/`npm` on PATH). Delete that folder before you reply. Never run a real `git push`, never create `.claude-push-token` in a real repo, never start a real browser, never touch real credentials. If a command of yours contains push text, a real guard hook may check it; put such tests in a script file and run the file.
- Claims about what an external tool does or defaults to (Playwright CLI, Chromium, npm, git, curl, gh/glab): check the tool's own docs or source on the web, never this snapshot's docs.
- Keep your context small: grep and `sed -n` for the lines you need; do not re-read files.

## Task

For every finding in the reports (duplicates across reports count once):

1. State what would have to be true for the finding to be wrong.
2. Check that, by running it where you can, otherwise by reading.
3. Verdict: SURVIVES (with the evidence that held), REFUTED (with the evidence), or UNSETTLED (what would settle it). Adjust severity if the evidence says the consequence is bigger or smaller than claimed.

## Report

Write to the path in your prompt, then reply with only that path.

1. One table row per finding: id(s), claim in a few words, verdict, severity after check, measured or derived, one-line evidence.
2. Counts: survives / refuted / unsettled, and severity changes.
3. Leftovers: anything you created that still exists, with its path (or "none").

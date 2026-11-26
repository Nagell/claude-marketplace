# Proposal

## Why

`review-mr` keeps its `run.json` and the agents' reports only in the session scratchpad under `/tmp/claude-<uid>/`. The next review in the same session overwrites `run.json`, and a reboot wipes the folder. On 2026-11-26 the `usage` report found a `run.json` for 0 of 93 review runs in the last 30 days, so it could not say which review agents add nothing unique and could not read what the review agents reported.

## What Changes

- Each `review-mr` run gets its own folder that outlives the session: `~/.local/share/review-runs/<project dir>/<session id>/<run id>/`. The run writes `run.json` and every agent report (`wave<n>-<slice>.txt`, Codex results included) there from the start of the run, so a run stopped halfway still leaves what it had.
- Nothing deletes these folders automatically. The user deletes them by hand. Claude Code's `cleanupPeriodDays` and `/base:cleanup` do not touch them.
- The end-of-run sweep keeps deleting the run's temp dir in the scratchpad and never the run folder.
- The `usage` report reads `run.json` from the run folders, one per run, and falls back to the session scratchpad for runs made before this change. Several reviews in one session each keep their own `run.json`.
- The run folder and its files are written with the Write tool, which the Bash sandbox does not restrict. Bypass mode needs no setting; other permission modes need one allow rule, documented in the README. `$XDG_DATA_HOME` replaces `~/.local/share` when set. A run that cannot write its folder stops before any agent starts instead of falling back to the scratchpad.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `review-mr-run`: a new requirement for the per-run folder that outlives the session; the sweep requirement gains a scenario that the run folder stays.
- `review-mr-agents`: agent reports are written to the run folder instead of the session scratchpad.
- `usage-report`: review runs are labelled from the run folders' `run.json`, one per run, with the scratchpad as a fallback.

## Impact

- `plugins/base/skills/review-mr/SKILL.md` and its agent briefs: the run folder path, `run.json` and report locations, the Codex result path, the sweep.
- `plugins/base/skills/usage/scripts/report.py`, `SKILL.md` and tests: where `run.json` is read and how a run folder is matched to a run.
- Disk use: tens of KB per run, kept until the user deletes it. The reports quote code from the reviewed repos.

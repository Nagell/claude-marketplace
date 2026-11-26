# Design

## Context

See proposal.md - Why. Today `review-mr` (`plugins/base/skills/review-mr/SKILL.md`) writes `$SCRATCH/run.json` and has every agent write `$SCRATCH/wave<n>-<slice>.txt`; `$SCRATCH` is the session scratchpad under `/tmp/claude-<uid>/<project dir>/<session id>/scratchpad`. The run's temp dir (`mktemp -d -p "$SCRATCH"`) holds throwaway work and is swept at the end. `usage/scripts/report.py` reads `<scratch root>/<project>/<session>/scratchpad/run.json`, one per session, and gives it to the run whose agents it lists, else to the session's latest review run.

The Bash sandbox allows writes only to the working directory, `$TMPDIR` and `/tmp`, plus `~/.claude/debug` and `~/.claude/plugins`; everything else under `~/.claude` is read-only to sandboxed commands. The Write tool is not bound by that rule (decision 4).

## Goals / Non-Goals

**Goals:**
- Every review run's `run.json` and agent reports survive the session, a reboot and Claude Code's transcript sweep.
- A run stopped halfway keeps what it wrote.
- The `usage` report finds the right `run.json` for each run, including several runs in one session.

**Non-Goals:**
- Automatic deletion or a retention setting for run folders.
- Moving throwaway files (diffs, thread dumps, the run's temp dir) out of the scratchpad.
- Recovering runs from before this change beyond what the scratchpad fallback already gives.

## Decisions

### 1. Location: `~/.local/share/review-runs/<project dir>/<session id>/<run id>/`

The root is `$XDG_DATA_HOME/review-runs` when `XDG_DATA_HOME` is set, else `~/.local/share/review-runs`, the per-user data folder on Linux (WSL included) and a common one on macOS. `<project dir>` and `<session id>` mirror the transcript layout, so `report.py` maps a transcript session to its run folders without an index.

Rejected:
- Transcripts as the source (script extracts `run.json` and reports from tool calls). Ties the data to `cleanupPeriodDays`, which a different machine or a company policy can shorten; the user wants the history independent of it.
- `~/.claude/review-runs/`. Measured on 2026-11-26: in `default` and `acceptEdits` modes Claude Code refuses every Write under `~/.claude/` as a sensitive file, the main session's included, and an `Edit(...)` allow rule does not lift it. Only bypass mode could write there.
- Inside `~/.claude/projects/<project dir>/<session id>/`. Same refusal, and Claude Code's transcript sweep owns that tree.

### 2. Write in place from the start, no copy at the end

The run folder is created in step 2a, where `run.json` starts today, and is the only home of `run.json` and of every `wave<n>-<slice>.txt` (Codex results included). Every `$SCRATCH/run.json` and `$SCRATCH/wave…` reference in `SKILL.md` (six today) moves to the run folder; briefs carry its absolute path. Throwaway files stay in `$SCRATCH`.

Rejected: copy at the end. A run the user stops, or a session that dies, would lose everything, which is the failure this change exists to fix.

### 3. Run id

`<UTC start, yyyymmddThhmmssZ>-<platform>-<mr iid>`, for example `20261126T101540Z-gitlab-19660`. Unique within a session, sorts by time, and readable when browsing. `run.json` keeps its existing fields; `run_dir` is added so sweep commands and the `usage` report can quote the literal path.

### 4. The Write tool creates the folder and every file in it

Measured on 2026-11-26 on macOS: in bypass mode the main session's Write and a general-purpose Haiku subagent's Write both created files with their parent folders, without a prompt; a sandboxed Bash `mkdir -p` outside the working directory and `/tmp` failed with `Operation not permitted`. In `default` mode a Write to `~/.local/share/<…>` passed with the allow rule `Edit(//<home>/.local/share/review-runs/**)` (an allow rule for file writes must be written as `Edit(...)`; `Write(...)` is not matched). So the main session creates the run folder by writing `run.json` with Write, agents write their reports with Write, and no Bash command writes, moves or deletes anything in the run folder. Reading it from Bash (`cat`, `report.py`) works, since reads are allowed. The README documents the allow rule for non-bypass modes.

Rejected: a sandbox write exception for the run root in the user's settings. Not needed, since Bash never writes there.

The existing rule stays: an agent whose Write is refused replies with the report text, and the main session saves it.

### 5. Unwritable folder stops the run

If the Write of `run.json` fails at step 2a, the run stops before any agent starts and names the path and the allow rule from decision 4. Falling back to the scratchpad would silently recreate the data loss.

### 6. `usage` report reads run folders first

`report.py` lists `~/.local/share/review-runs/<project>/<session>/*/run.json` for each scanned session. A run is matched to the folder whose agents it ran; a folder whose agents match no run goes to the latest run that started at or before the time in its name, since the run creates its folder after it starts. A folder before every run is reported in `errors`, not guessed. Folders that list agents are placed first, so they win over an empty folder of the same run; a second folder for a run that is already labelled is reported in `errors` and never handed to an earlier run. A scratchpad `run.json` whose agents belong to a run a folder labelled is a stray copy and is ignored. Folders older than the report window are skipped, since their runs are not in the scan. The scratchpad `run.json` is read only for runs that no folder matched. `run.json` `report` paths point into the run folder, so the deep read opens reports that still exist. The run-folder root is a parameter (`--runs-root`, default `~/.local/share/review-runs`) so tests use fixtures.

### 7. No retention

Nothing deletes run folders. `/base:cleanup` already scans only `/tmp/claude-<uid>`, the repo and its worktrees, so it needs no change.

## Risks / Trade-offs

- [Reports quote code from company repos and are kept with no expiry] → The skill's README states where they live and that deleting them is manual; the user decided this knowingly.
- [A model reaches for Bash `mkdir` or `cp` into the run folder and the sandbox refuses it] → `SKILL.md` says the folder is written only with Write, and the stop rule (decision 5) names the cause.
- [Write prompts in default or acceptEdits mode] → The README documents the one allow rule that lifts it.
- [Linux/WSL not measured] → Same Write tool and same path convention; the first review there shows it, and the stop rule names the path if it fails.
- [A model writes `run.json` back to `$SCRATCH` out of habit] → All six references change in one edit, and the stop rule names the folder; a test in `usage` covers a run whose `run.json` is only in the scratchpad.
- [Disk grows without bound] → Tens of KB per run, about 100 runs a month at the current rate.

## Migration Plan

No data migration. Old runs keep working through the scratchpad fallback while their scratchpads exist. Rollback is reverting the plugin release; run folders already written stay and are ignored.

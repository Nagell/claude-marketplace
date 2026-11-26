# Spec Delta

## ADDED Requirements

### Requirement: Run folder kept after the session
At its start each run SHALL create its own folder at `~/.local/share/review-runs/<project dir>/<session id>/<run id>/` (`$XDG_DATA_HOME/review-runs/…` when that is set) and write `run.json` there with the Write tool, keeping it current for the whole run. `<run id>` SHALL be unique within the session and SHALL start with the run's UTC start time. The skill SHALL NOT delete run folders, and SHALL NOT write `run.json` to the session scratchpad.

#### Scenario: Two reviews in one session
- **WHEN** a session runs `review-mr` twice
- **THEN** the session's folder under `~/.local/share/review-runs/` holds two run folders, each with its own `run.json`

#### Scenario: Run stopped early
- **WHEN** the user stops a run after wave 1
- **THEN** its run folder still holds `run.json` and the wave 1 reports written so far

#### Scenario: Reboot
- **WHEN** the machine reboots after a run
- **THEN** the run folder and everything in it are still there

### Requirement: Run folder not writable
When the run folder cannot be created or written, the main session SHALL stop before any agent starts and say which path failed, and SHALL NOT fall back to the session scratchpad.

#### Scenario: Write refused
- **WHEN** writing `run.json` into `~/.local/share/review-runs/<project dir>/<session id>/<run id>/` is refused
- **THEN** the run stops and names that path, and no agent has started

## MODIFIED Requirements

### Requirement: Sweep at the end
Before finishing, the main session SHALL read every `Leftovers:` line, stop processes whose command line contains the run's temp dir, delete that dir after confirming its real path is inside `$SCRATCH`, and remove the throwaway base worktree from the checks step. Every sweep command SHALL use the literal paths from `run.json`, since shell variables do not persist between Bash calls, and SHALL refuse to run when its path is empty; `pgrep` or `pkill` SHALL never run with an empty pattern.

#### Scenario: Temp dir path lost
- **WHEN** a sweep command's path is empty
- **THEN** the command exits before it stops or deletes anything

#### Scenario: Process left running
- **WHEN** a Chrome started by an agent still runs with the run's temp dir in its command line
- **THEN** the sweep stops it

#### Scenario: Temp dir removed
- **WHEN** the run ends
- **THEN** the run's temp dir no longer exists

#### Scenario: Run folder stays
- **WHEN** the sweep finishes
- **THEN** the run folder under `~/.local/share/review-runs/` and every file in it are unchanged

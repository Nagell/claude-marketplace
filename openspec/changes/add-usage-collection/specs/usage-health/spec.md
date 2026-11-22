# Spec Delta

## Purpose

Make a broken background collector visible. Transcript format is undocumented and changes between Claude Code versions, so silent failure must be detected and reported to the user.

## ADDED Requirements

### Requirement: Schema validation
Every collector run SHALL validate the transcript fields it relies on: parseable JSON lines, and on assistant lines a message id, model, timestamp and usage with the four token classes. It SHALL record the parse-failure ratio, the missing-field ratio and unknown entry types.

#### Scenario: Parse failures
- **WHEN** more than 1% of newly read lines (at least 5) fail to parse
- **THEN** the run state is `warn` with code `parse_failures`

#### Scenario: Missing usage fields
- **WHEN** more than 1% of newly read assistant lines lack a required field
- **THEN** the run state is `warn` with code `missing_fields` and the field names

#### Scenario: Zero usage on an active day
- **WHEN** a day has user or assistant lines but no usage rows
- **THEN** the run state is `error` with code `no_usage_parsed`

#### Scenario: Unknown entry type
- **WHEN** a line has an entry type never seen before
- **THEN** it is counted and listed as informational and does not change the state

### Requirement: Status file
Each run SHALL write `~/.claude/usage/status.json` with state (`ok`, `warn`, `error`), start and finish times, counts of files and lines, a list of problems (code, message, count, first seen) and the time of the last `ok` run. A run that started and never finished SHALL be reported as crashed by the next run.

#### Scenario: Clean run
- **WHEN** a run finds no problem
- **THEN** state is `ok` and the problem list is empty

#### Scenario: Crash
- **WHEN** a run is killed before it writes its final status
- **THEN** the next run records problem `crashed` with the previous start time

#### Scenario: Diagnostics without content
- **WHEN** a problem is recorded
- **THEN** `~/.claude/usage/diagnostics.jsonl` gets the file path, line number and the key names of the offending entry, not its values

### Requirement: Escalation into the next session
At session start the hook SHALL read the status file. When the state is `warn` or `error`, it SHALL return `additionalContext` that tells the model to tell the user in one line at the start of its first reply and to offer `/usage-investigate`. The same problem set SHALL be announced at most once per local day.

#### Scenario: Problem present
- **WHEN** the last status is `error` and it has not been announced today
- **THEN** the session starts with a context note naming the problem codes and the investigate command

#### Scenario: Already announced
- **WHEN** the same problems were announced earlier today
- **THEN** no note is injected

#### Scenario: Recovered
- **WHEN** the last status is `ok`
- **THEN** nothing is injected

#### Scenario: Stale collector
- **WHEN** the status file is missing or older than three days while transcripts exist
- **THEN** the hook injects a note that collection has not run

### Requirement: Investigation command
A user-invoked skill `usage-investigate` SHALL start one background agent. The agent reads the status file, the diagnostics and the newest transcript shapes, writes findings to `~/.claude/usage/investigations/YYYY-MM-DD.md` and reports where. It SHALL NOT edit plugin code or the dataset.

#### Scenario: Investigation requested
- **WHEN** the user runs `/usage-investigate`
- **THEN** a background agent starts and the user can keep working

#### Scenario: Findings
- **WHEN** the agent finishes
- **THEN** the findings file names the changed field or shape, the Claude Code version that introduced it where visible and a proposed parser fix

# Spec Delta

## Purpose

Give a stable, human-readable view of each day's usage, and let the user rebuild and read any day on demand.

## ADDED Requirements

### Requirement: Fixed-format daily file
The collector SHALL render one Markdown file per active local day at `~/.claude/usage/daily/YYYY-MM-DD.md`, always with the same shape: a title line, a summary paragraph built from counts and one table with fixed columns. New information goes into the Flags column, never into new columns.

#### Scenario: Active day
- **WHEN** a day has activity
- **THEN** its file has the title, the summary paragraph and the table with columns Project, Task, Main model@effort, Agents, Requests, Input+cache write, Cache read, Output, Est. USD, Flags

#### Scenario: Idle day
- **WHEN** a day has no activity
- **THEN** no file is written for it

#### Scenario: Touched days only
- **WHEN** a run adds lines for one day
- **THEN** only that day's file is rewritten

### Requirement: Summary from counts
The summary paragraph SHALL state sessions, projects, requests (main and agents), agent count by model, compactions by trigger, estimated cost with the price table version and how many sessions continued from earlier days. It SHALL be built from counts by a template, without an LLM.

#### Scenario: Estimate labelled
- **WHEN** a daily file shows cost
- **THEN** the summary names it an API-equivalent estimate at a stated price table version

### Requirement: One row per session and task
The table SHALL have one row per session and task title for the day. Agents SHALL be rolled into their parent row, with the per-agent split kept in the dataset. Task label SHALL be the latest session title at or before that day, else the skill, then PR or branch, then the agent description.

#### Scenario: Agents rolled up
- **WHEN** a session ran nine agents on a day
- **THEN** the day has one row for it and the Agents column shows the count with model@effort groups

#### Scenario: Flags
- **WHEN** a session had earlier active days or was compacted
- **THEN** the Flags column says "continued" or "compacted xN"

### Requirement: On-demand re-collect skill
A skill `usage-report` SHALL re-collect a given local day (default today and yesterday) and show that day's file. A re-collect SHALL replace the rows of the affected sessions from their transcripts and SHALL NOT delete rows whose transcripts no longer exist.

#### Scenario: Show yesterday
- **WHEN** the user runs the skill with no argument
- **THEN** the collector runs for today and yesterday and the skill prints yesterday's file path and table

#### Scenario: Transcript already swept
- **WHEN** a day's transcripts were deleted by the retention sweep
- **THEN** a re-collect leaves that day's existing rows and file unchanged and says why

#### Scenario: No data
- **WHEN** the requested day has no rows
- **THEN** the skill says so and names the first and last day in the dataset

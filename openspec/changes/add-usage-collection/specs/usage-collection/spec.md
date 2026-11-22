# Spec Delta

## Purpose

Turn Claude Code session transcripts into a durable, correct, per-day usage dataset without slowing the main session and without an LLM.

## ADDED Requirements

### Requirement: Detached, non-blocking trigger
A `SessionStart` hook SHALL start the collector as a detached background process and return without waiting for it. The hook SHALL finish in well under one second and SHALL NOT call an LLM. No scheduler is required.

#### Scenario: Session starts
- **WHEN** a session starts and no collector run is in progress
- **THEN** the hook returns immediately and a collector process keeps running after the hook has exited

#### Scenario: Recent run
- **WHEN** the last collector run finished less than five minutes ago
- **THEN** the hook does not start another run

#### Scenario: Collector already running
- **WHEN** a collector run holds the lock
- **THEN** a second run exits at once without touching the dataset

#### Scenario: Opt-out
- **WHEN** the environment variable `CLAUDE_USAGE_COLLECT` is `0`
- **THEN** the hook starts nothing and injects nothing

### Requirement: Incremental scanning with a ledger
The collector SHALL keep a ledger of every transcript file it has scanned, with size, modification time and the byte offset of the last fully parsed line. It SHALL skip unchanged files and read grown files only from the stored offset.

#### Scenario: Unchanged file
- **WHEN** a file's size and modification time match the ledger
- **THEN** the file is not opened

#### Scenario: Grown file
- **WHEN** a transcript has new lines after the stored offset
- **THEN** only the new lines are parsed and the offset moves to the end of the last complete line

#### Scenario: Partial last line
- **WHEN** the last line of a file is incomplete because a session is writing it
- **THEN** that line is left for the next run

#### Scenario: Rewritten file
- **WHEN** a file is smaller than its stored offset or its first bytes no longer match the ledger
- **THEN** every row of that session is rebuilt from the session's files and the status file records a warning

### Requirement: Dedupe by message id
The collector SHALL count each API response once. A response written as several transcript lines SHALL be counted by its `message.id`, including when the lines span two runs.

#### Scenario: Split response
- **WHEN** one response appears as three lines with the same `message.id` and identical usage
- **THEN** its tokens are counted once

#### Scenario: Response straddles a run boundary
- **WHEN** the first block of a response is read in one run and the next block in the following run
- **THEN** the response is still counted once

### Requirement: Local-day attribution per message
The collector SHALL attribute each message's tokens to the local calendar day of that message's own timestamp. A session that spans several days SHALL produce rows on each day it was active and none on idle days. Compaction SHALL be recorded as an event on the day of its boundary line and SHALL NOT move tokens.

#### Scenario: Multi-day session
- **WHEN** one session file has messages on three different local days
- **THEN** each day gets its own row for that session with only that day's tokens

#### Scenario: Late evening in UTC
- **WHEN** a message is stamped 23:30 UTC and the local zone is UTC+1
- **THEN** it counts on the next local day

#### Scenario: Compaction
- **WHEN** a session is compacted on a day
- **THEN** that day's row records one compaction with trigger and token counts and no token is re-attributed

### Requirement: Subagent transcripts are tracked and linked
The collector SHALL scan subagent transcripts under each session and record, per agent, its type, description, requested model, effort and parent session from the agent's meta file. Subagent tokens SHALL be counted in the day of each message.

#### Scenario: Agent with meta file
- **WHEN** a session has an agent transcript and a meta file
- **THEN** the agent's rows carry its description, model alias, effort and parent session id

#### Scenario: Agent transcript missing its meta file
- **WHEN** the meta file is absent
- **THEN** the agent's rows are still written, with the missing fields empty, and the status file records an informational note

### Requirement: Dataset and token classes
The collector SHALL write JSONL rows under `~/.claude/usage/data/`, one file per month, keyed by day, session, agent, model, effort, speed and prompt tier. Each row SHALL keep input, 5-minute cache write, 1-hour cache write, cache read, output and thinking tokens as separate counts. Tokens are the source of truth; estimated USD is derived.

#### Scenario: Token classes kept apart
- **WHEN** a day has cache reads far larger than other classes
- **THEN** the row stores each class separately and no single "total tokens" value is stored

#### Scenario: Atomic write
- **WHEN** the collector is killed while writing a month file
- **THEN** the previous complete file is still readable

### Requirement: Price table and estimated cost
The collector SHALL compute estimated USD per request from a price table and SHALL store the table version on each row. The table is the user's `~/.claude/usage/prices.json` when present, else the seed shipped with the plugin. A model absent from the table SHALL get a null estimate and a flag, not a guess.

#### Scenario: Long-prompt tier
- **WHEN** a request to a model with a long-prompt price tier has a prompt above the tier threshold
- **THEN** the request is priced and stored under the long-prompt tier

#### Scenario: Unpriced model
- **WHEN** a message names a model that is not in the table
- **THEN** the row has `est_usd` null, an unpriced flag and a warning in the status file

#### Scenario: Reprice
- **WHEN** the price table changes and the collector is run with the reprice option
- **THEN** every row's estimate and table version are recomputed from its stored tokens

### Requirement: Platform and runtime support
The collector and hook SHALL run on Linux, WSL and macOS with python3 (standard library only) and POSIX `sh`. They SHALL NOT rely on GNU-only tools or `setsid`. The transcript and data roots SHALL follow `CLAUDE_CONFIG_DIR` when it is set, else `~/.claude`.

#### Scenario: macOS
- **WHEN** the hook runs on macOS with the system python3
- **THEN** it starts a detached collector without `setsid` and without GNU coreutils

#### Scenario: python3 missing
- **WHEN** python3 is not on `PATH`
- **THEN** the hook injects one line saying so and exits 0

### Requirement: Privacy of stored data
The collector SHALL write only under the data root outside any repository. It SHALL NOT store prompt text, file contents or tool arguments. It MAY store session title, project directory name, git branch, PR number and agent description.

#### Scenario: Prompt text
- **WHEN** a transcript contains user prompts
- **THEN** no prompt text appears in the dataset, the daily files or the status file

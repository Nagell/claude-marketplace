# Spec Delta

## Purpose

Read Claude Code transcripts on demand and turn them into correct per-run, per-agent request counts, token counts and estimated cost. Every mode of the `usage` skill uses this one copy; no other skill prices requests.

## ADDED Requirements

### Requirement: On-demand transcript reading
The scanner SHALL read session transcripts at `~/.claude/projects/<project>/<session>.jsonl` and agent transcripts at `<session>/subagents/agent-<id>.jsonl` with their `.meta.json` files, only when it is run. It SHALL NOT need a hook, a background job or a stored ledger. It SHALL only read transcripts and SHALL NOT change them.

#### Scenario: Run on demand
- **WHEN** the user runs the scanner for a 30-day window
- **THEN** it reads the transcript files with activity in that window and prints its result without writing any file

#### Scenario: Agent without a meta file
- **WHEN** an agent transcript has no `.meta.json`
- **THEN** its requests are still counted and its role, requested model and effort are empty

### Requirement: Count each response once
The scanner SHALL count each API response once by its `message.id`, with one set of ids for the whole scan, across all files. A response written as several lines SHALL count as one request. Its token counts SHALL be the largest value of each usage field over its lines.

#### Scenario: Split response
- **WHEN** one response appears as three lines with the same `message.id` and the same usage
- **THEN** it counts as one request and its tokens are counted once

#### Scenario: Resumed session
- **WHEN** two session files hold lines with the same `message.id`
- **THEN** each shared id counts once, in the file with the earlier first timestamp

#### Scenario: Growing first line
- **WHEN** a response's first line has `output_tokens` 1 and its last line has 335
- **THEN** the request counts 335 output tokens

### Requirement: Synthetic lines
The scanner SHALL NOT price assistant lines whose `message.model` is `<synthetic>`. These are API error placeholders. It SHALL report their count as API errors and SHALL NOT list `<synthetic>` as an unpriced model.

#### Scenario: Error placeholder
- **WHEN** a session has two `<synthetic>` lines with zero tokens
- **THEN** the output shows two API errors and no unpriced model

### Requirement: Token classes kept apart
The scanner SHALL keep input, 5-minute cache write, 1-hour cache write, cache read and output tokens as separate counts. It SHALL NOT report a single total token number, because cache reads are far larger than the other classes.

#### Scenario: Cache-heavy run
- **WHEN** a run has cache reads a hundred times larger than its input tokens
- **THEN** the output shows each token class on its own

### Requirement: Skill runs and their agents
The scanner SHALL group requests into skill runs. A run is a stretch of one session that works for one skill, from its invocation until the next typed prompt. An assistant line without `attributionSkill` inside an open run SHALL stay in that run. A skill loaded inside an open run SHALL stay in that run. Each agent started inside a run SHALL belong to that run. A nested agent SHALL belong to its parent agent's run through `parentAgentId`. Requests outside any skill SHALL be grouped as "no skill".

#### Scenario: Skill with agents
- **WHEN** a session invokes `review-mr` and the run starts nine agents
- **THEN** the scanner reports one `review-mr` run with nine agents and their requests

#### Scenario: Same skill twice
- **WHEN** one session runs `review-mr`, the user types a new prompt, and `review-mr` is invoked again
- **THEN** the scanner reports two runs

#### Scenario: Reply typed during a run
- **WHEN** the run's last turn asks the user something, the user answers, and the next lines carry no skill and no new invocation
- **THEN** the scanner reports one run that includes those lines

#### Scenario: Nested skill
- **WHEN** a `review-mr` run loads `writing-style-guide` and then continues as `review-mr`
- **THEN** the scanner reports one `review-mr` run that lists `writing-style-guide` as nested

#### Scenario: Gaps in attribution
- **WHEN** a run has attributed assistant lines with unattributed ones between them and no typed prompt
- **THEN** all those lines belong to the one run

#### Scenario: Nested agent
- **WHEN** an agent at `spawnDepth` 2 has a `parentAgentId` that points to an agent of a `review-mr` run
- **THEN** the nested agent belongs to that `review-mr` run

### Requirement: Typed prompt detection
A typed prompt SHALL be a user line with `origin.kind` `human`. When `origin` is missing, it SHALL be a user line with string content that is not `isMeta`, not a tool result, and does not start with `<task-notification>`, `<local-command` or `<bash-`. A task notification or peer message SHALL NOT end a run.

#### Scenario: Background agent finishes mid-run
- **WHEN** a `<task-notification>` user line with `origin.kind` `task-notification` appears in the middle of a `review-mr` run
- **THEN** the run continues and its later agents belong to it

### Requirement: Run start without attribution
When assistant lines lack `attributionSkill`, a run SHALL start at a `Skill` tool_use or at a `<command-name>` line for a skill command. A command is a skill command when its name contains `:`, is not built in, or the lines after it carry `attributionSkill` or the skill-load meta line. Built-in commands SHALL NOT start a run.

#### Scenario: Clear command
- **WHEN** a session without `attributionSkill` has a `<command-name>` line for `/clear`
- **THEN** no run starts and its requests stay under "no skill"

### Requirement: Per-agent details
For each agent in a run the scanner SHALL report its role (agent type and description), the model it actually used, its effort, requests, token classes, largest prompt, requests over 100k prompt tokens, duration, estimated cost, the number of lines starting with `Unfinished:` in its final reply and its report file, and the meta `finished` field when present. The `Unfinished:` count SHALL apply to `review-mr` only; for other skills it SHALL be n/a.

#### Scenario: Agent overwhelmed
- **WHEN** an agent's final reply starts with an `Unfinished:` line and its largest prompt is 140k tokens
- **THEN** its details show one `Unfinished:` line, a largest prompt of 140k and its count of requests over 100k

#### Scenario: Convention not used
- **WHEN** a skill other than `review-mr` runs agents
- **THEN** that skill's agents show the `Unfinished:` count as n/a

#### Scenario: Line in the report file
- **WHEN** a `review-mr` agent writes `Unfinished: a.py` into its report file and replies with only the path
- **THEN** its details show one `Unfinished:` line

### Requirement: Prompt size and long-prompt tier
The scanner SHALL measure each request's prompt as input plus cache write plus cache read tokens. When the model's price entry has a long-prompt tier, a request whose prompt is above the tier threshold SHALL be priced at that tier. Haiku 5.5 has such a tier above 100k tokens.

#### Scenario: Haiku over the threshold
- **WHEN** a Haiku 5.5 request has 2k input, 3k cache write and 115k cache read tokens
- **THEN** its prompt is 120k and it is priced at the long-prompt tier

#### Scenario: Haiku under the threshold
- **WHEN** a Haiku 5.5 request has a prompt of 80k tokens
- **THEN** it is priced at the base tier

### Requirement: Price table with user override
The scanner SHALL price requests from the seed price table shipped with the plugin. When `~/.claude/usage/prices.json` exists and is valid, it SHALL merge over the seed per model id. An invalid override SHALL be reported and the seed used alone. The scanner SHALL NOT fetch prices from the network. Output SHALL name the seed version and, when used, the override version.

#### Scenario: Partial override
- **WHEN** a valid override lists only Haiku 5.5
- **THEN** Haiku 5.5 uses the override prices, Opus 5.5 keeps its seed prices, and both table versions are shown

#### Scenario: Dated model id
- **WHEN** a request names `claude-haiku-4-5-20251001` and the table has `claude-haiku-4-5`
- **THEN** it is priced as `claude-haiku-4-5`

#### Scenario: Unpriced model
- **WHEN** a request names a model that is in neither table
- **THEN** its cost is null, its tokens are still counted and the output lists the model as unpriced

### Requirement: Reusable pricing
The scanner SHALL expose its price lookup, its per-request cost and a per-agent summary function as importable Python functions. The summary function SHALL take one agent transcript path and return its deduped requests, token classes, prompt sizes and cost. Every `usage` mode SHALL use it instead of its own dedupe, token parsing, table or tier rule.

#### Scenario: Report prices a review agent
- **WHEN** the report prices one agent listed in a `review-mr` `run.json`
- **THEN** its numbers are the scanner's numbers for that agent, which come from the summary function

### Requirement: Tolerant parsing
The scanner SHALL skip a line it cannot parse, or a line that lacks a field it needs, and SHALL report the number of skipped lines in its output. It SHALL NOT stop or alert on a threshold.

#### Scenario: Truncated last line
- **WHEN** a session is still writing and the last line of its transcript is incomplete
- **THEN** the scanner skips that line and reports one skipped line

### Requirement: Platforms and runtime
The scanner SHALL run with python3 3.9 or newer and the standard library only, on Linux, macOS and WSL. 3.9 matches the macOS system Python.

#### Scenario: Minimal machine
- **WHEN** only python3 3.9 with no extra packages is installed
- **THEN** the scanner and its tests run

# Spec Delta

## Purpose

Show the user what their most used skills and agents cost on this machine, how that changes over time, and which agents to drop or strengthen, from local transcripts and on demand.

## ADDED Requirements

### Requirement: User-invoked skill with a mode choice
The `usage` skill in plugin `base` SHALL run only when the user invokes it. It SHALL first ask, with AskUserQuestion, which mode to run: `report`, marked recommended and listed first, or `models`.

#### Scenario: Skill started
- **WHEN** the user invokes `usage`
- **THEN** the skill asks for the mode with `report (Recommended)` as the first option

### Requirement: Models mode not available yet
Until a later change adds it, the `models` option SHALL say in its label or description that it is not available yet. When the user picks it, the skill SHALL say so and offer `report` instead.

#### Scenario: User picks models
- **WHEN** the user picks `models`
- **THEN** the skill says the mode is not available yet and offers to run `report`

### Requirement: Top skills by spend
The `report` mode SHALL rank skills by estimated spend in a window and report the top ones, each with its agents. Defaults are a 30-day window and the top 5 skills. The user SHALL be able to change both. All skills count, not only review skills.

#### Scenario: Default report
- **WHEN** the user runs `report` with no options
- **THEN** the report covers the 5 skills with the highest estimated spend in the last 30 days

#### Scenario: Fewer skills than the limit
- **WHEN** only three skills ran in the window
- **THEN** the report covers those three and says so

### Requirement: Script-built trends
For each top skill a script SHALL aggregate every run in the window: cost per run, cost per agent role, cost by model and effort, the share of requests over 100k prompt tokens, and totals per month. No LLM SHALL compute these numbers.

#### Scenario: Trend table
- **WHEN** `review-mr` ran 12 times over two months
- **THEN** the report shows its cost per run, per role, per model and effort, its over-100k share and one line per month, all from the script output

### Requirement: Review runs labelled from run.json
The `report` mode SHALL be the only place that prices `review-mr` runs. When a session's scratchpad holds a valid `review-mr` `run.json`, the report SHALL label each agent it lists by role and slice, matched by agent id, show the requested model and effort next to the actual model, and show per role the cost and the number of surviving findings that role found first. Agents the file does not list, and runs with no `run.json`, SHALL keep the meta-file labels.

#### Scenario: Run with run.json
- **WHEN** a `review-mr` run's scratchpad holds `run.json` with three slice owners and a refuter, and two surviving findings name `slice-2` as source
- **THEN** the report labels the agents `slice-owner slice-1` to `slice-3` and `refuter`, and shows cost per role with two unique surviving findings for `slice-owner`

#### Scenario: Repeated finding
- **WHEN** a surviving finding has source `slice-2` and duplicates `runit`
- **THEN** it counts as unique for `slice-owner` and as repeated for `runit`

#### Scenario: No run.json
- **WHEN** the scratchpad of a `review-mr` session was swept
- **THEN** the run is still priced and its agents keep their meta-file labels

#### Scenario: Codex agent
- **WHEN** `run.json` lists an agent with model `codex`
- **THEN** the report lists it with no cost, because it has no Claude transcript

### Requirement: Deep read of recent runs and outliers
The model SHALL read the per-agent details of the last 5 runs of each top skill, and of outlier runs in the window: the most expensive run, the run with the most `Unfinished:` lines and the run with the largest prompt. When the `Unfinished:` count is n/a for a skill, that outlier SHALL be skipped. The user SHALL be able to change the number of recent runs.

#### Scenario: Custom run count
- **WHEN** the user asks for the last 3 runs
- **THEN** the deep read covers 3 recent runs per top skill plus the outliers

#### Scenario: Convention not used
- **WHEN** a top skill's agents show the `Unfinished:` count as n/a
- **THEN** the deep read has no most-`Unfinished:` outlier for that skill and says why

#### Scenario: Outlier is also recent
- **WHEN** the most expensive run is one of the recent runs
- **THEN** it is read once and marked as both

### Requirement: Drop and strengthen candidates
From the deep read the model SHALL name agent roles to drop, because they add nothing the other agents do not, and roles to strengthen, because the model looks overwhelmed. Signs of overwhelm are prompts over 100k tokens, `Unfinished:` lines and files left unread. Each candidate SHALL cite the runs it rests on.

#### Scenario: Role to strengthen
- **WHEN** a role ends with `Unfinished:` lines in 4 of 5 recent runs
- **THEN** the report lists it as a candidate to strengthen and names those runs

#### Scenario: Role to drop
- **WHEN** a role's findings were all found by other agents in the same runs
- **THEN** the report lists it as a candidate to drop and names those runs

### Requirement: Recommendations are output only
The report SHALL NOT change any skill, agent or setting to apply a recommendation. It SHALL say that applying one goes through an OpenSpec change and a benchmark check.

#### Scenario: Report ends
- **WHEN** the report lists candidates
- **THEN** no skill or agent file changed and the report names the OpenSpec change and benchmark step

### Requirement: Output stays out of repositories
The skill SHALL print the report in the session. It SHALL NOT write report or usage data into any repository.

#### Scenario: Run inside a repo
- **WHEN** the user runs `usage` from a git working tree
- **THEN** no file in that working tree is created or changed

### Requirement: Retention check
Every run SHALL read `cleanupPeriodDays` from `~/.claude/settings.json`. When it is unset, invalid or from 1 to 179, the skill SHALL measure the average transcript size per day, estimate the disk use at 180 days and offer to set 180. Claude Code reports 0 and other values below 1 as a settings error, so the skill SHALL call them invalid, count them as 30 and say so. It SHALL change the setting only after the user agrees.

#### Scenario: Short retention
- **WHEN** `cleanupPeriodDays` is unset
- **THEN** the skill shows the size per day and the estimate at 180 days, and asks before it writes `cleanupPeriodDays: 180`

#### Scenario: User declines
- **WHEN** the user says no to the offer
- **THEN** `~/.claude/settings.json` is unchanged

#### Scenario: Invalid value
- **WHEN** `cleanupPeriodDays` is 0
- **THEN** the skill says the value is invalid, counts it as 30 and offers 180

#### Scenario: Retention already long
- **WHEN** `cleanupPeriodDays` is 180 or more
- **THEN** the skill does not offer a change

# Spec Delta

## Purpose

Let the user decide, with evidence, which model and effort each task type should use when new models ship, and record that decision as a small, approved change to their CLAUDE.md files.

## ADDED Requirements

### Requirement: User-run, with a usable dataset
The `model-guidance` skill SHALL run only when the user invokes it. It SHALL depend on the usage dataset from `add-usage-collection` and SHALL first check that the dataset exists, the last collector status is `ok` and the dataset covers at least 14 active days. If not, it SHALL say what is missing and continue only on the evidence that is available.

#### Scenario: No dataset
- **WHEN** `~/.claude/usage/` has no data
- **THEN** the skill says so, offers to run `usage-report` first and does not propose cost-based rules

#### Scenario: Thin dataset
- **WHEN** the dataset covers fewer than 14 active days
- **THEN** the skill labels every usage figure "thin data" and proposes no rule from usage alone

### Requirement: Prices from the official page
The skill SHALL fetch current prices from `https://platform.claude.com/docs/en/about-claude/pricing` (the markdown form of the page), cross-check model ids and prices with the `claude-api` skill, and show a diff against the active price table: changed, added and retired models. A disagreement between the two sources SHALL be shown, with the page treated as authoritative.

#### Scenario: New models listed
- **WHEN** the page lists models that are not in the table
- **THEN** the diff shows them as added with all price classes and any long-prompt tier

#### Scenario: Sources disagree
- **WHEN** the `claude-api` skill gives a different price than the page
- **THEN** the diff shows both values and marks the row "check"

#### Scenario: Page unreachable
- **WHEN** the page cannot be fetched
- **THEN** the skill keeps the current table, says so and marks every cost figure with the table's age

### Requirement: Price table update needs approval
The skill SHALL write `~/.claude/usage/prices.json` only after the user approves the shown diff. After a write it SHALL tell the user to run the collector's reprice option, and SHALL report any model in the dataset that still has no price.

#### Scenario: Approved
- **WHEN** the user approves the diff
- **THEN** the table is written with a new version (the fetch date) and its source URL

#### Scenario: Declined
- **WHEN** the user declines
- **THEN** no file changes

### Requirement: Independent benchmark data per model and effort
The skill SHALL collect intelligence and coding-agent benchmark data from the sources in its source registry, including at least Artificial Analysis (Intelligence Index, cost to run, Terminal-Bench). Each datum SHALL carry model, effort level where the source gives one, the metric, the source URL and the fetch date. A source that fails SHALL be reported and skipped.

#### Scenario: Effort levels in the source
- **WHEN** a source lists a model at several effort levels
- **THEN** each model@effort pair is kept as its own datum

#### Scenario: No effort level in the source
- **WHEN** a source lists a model without effort
- **THEN** the datum is kept with effort "unspecified" and is not compared with effort-specific data

#### Scenario: Source down or changed
- **WHEN** a source fails to load or its layout no longer yields the expected fields
- **THEN** the skill names the source, continues with the others and lists it as a registry problem to fix

### Requirement: Source registry
The skill SHALL keep a registry of sources: URL, what it contributes, how it is read (API, HTML table, embedded data or browser needed), how stable that is, and the date it was last verified. Each run SHALL re-verify the sources it uses and update the dates.

#### Scenario: New source suggested
- **WHEN** the skill finds a current benchmark source that is not in the registry
- **THEN** it proposes the entry with the same fields and adds it only on approval

### Requirement: Real usage by task type
The skill SHALL read the dataset and report, per task type, the models and efforts actually used, requests, token classes, estimated cost and agents per task. Task types SHALL come from a short fixed list: review, implement, research, commit-chore, docs, other. The classification SHALL use rows' skill, branch prefix, agent type and title first; unlabelled titles MAY be classified by one batched cheap-model call after the user agrees, and the result SHALL be cached.

#### Scenario: Heuristic label
- **WHEN** a row's skill or agent type maps to a task type
- **THEN** the row is labelled without any model call

#### Scenario: Unlabelled rows
- **WHEN** rows remain unlabelled
- **THEN** the skill asks before spending any model call and reports how many rows and which model

### Requirement: Split guidance table
The skill SHALL propose guidance as a table of task type to tier and model@effort, where a tier (cheap, mid, top) maps to a model id in one line. It SHALL keep a task type on an older or cheaper model when the evidence shows it is good enough, and SHALL switch only the task types the evidence supports.

#### Scenario: Mixed outcome
- **WHEN** a new model beats the current one for review but not for commit-chore
- **THEN** the proposal changes the review row and leaves commit-chore on its current model

#### Scenario: Tier remap
- **WHEN** a new model replaces the one behind a tier
- **THEN** only the tier-to-model line changes and rules naming other tiers stay as they are

### Requirement: Evidence required for a rule
The skill SHALL propose a new or changed rule only with a quality signal: a benchmark result from this skill's runs, or an independent source that covers that task type. Cost and usage data alone SHALL only flag an outlier. A change to an existing rule SHALL need at least 30% lower cost at equal or better measured quality, or a clear quality gain at similar cost.

#### Scenario: Cost outlier only
- **WHEN** the dataset shows a task type is expensive but no quality signal exists
- **THEN** the skill reports it as an outlier and proposes no rule

#### Scenario: Evidence on the rule line
- **WHEN** a rule is proposed
- **THEN** it carries the evidence month and a review-by month

### Requirement: Approved diff to the CLAUDE.md files
The skill SHALL present the proposed change as a diff to the model-and-effort section of `~/.claude/CLAUDE.md` and of `plugins/base/CLAUDE.md`, and SHALL write each file only after the user approves that diff. Rules backed by broad evidence MAY go into the `base` template; personal preferences SHALL stay in the personal file. The section SHALL stay at about ten lines. Evidence SHALL go to `~/.claude/usage/guidance-log.md`, not into CLAUDE.md.

#### Scenario: Approval
- **WHEN** the user approves the personal diff and declines the template diff
- **THEN** only `~/.claude/CLAUDE.md` is edited

#### Scenario: Nothing to change
- **WHEN** the evidence supports no change
- **THEN** the skill says so, edits no file and still logs the run

#### Scenario: Plan window
- **WHEN** the skill reports cost
- **THEN** it states that USD is an API-equivalent estimate and not the share of the subscription window

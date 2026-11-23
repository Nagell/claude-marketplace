# Spec Delta

## Purpose

Say which model and effort each `review-mr` agent runs on, how the diff is cut into slices, and what every agent is told, so a review finds the high-severity bugs at a known cost.

## ADDED Requirements

### Requirement: Model and effort per role
The skill SHALL run wave-1 agents (slice owners, the contract agent, the run-it agent), wave-2 gap agents and the optional end-to-end simulation on Haiku 5.5 at max effort. It SHALL run refuters and thread validation on Opus at the base effort. Every Agent call SHALL state model and effort, and `run.json` SHALL record both with the model id resolved from the transcript.

#### Scenario: Default run
- **WHEN** the user starts a review with no `--fast`
- **THEN** slice owners run on Haiku at max effort and refuters on Opus at the effort answered in step 0

#### Scenario: Effort answer does not change Haiku
- **WHEN** the user answers `Low` in the effort question
- **THEN** Haiku agents still run at max and only the Opus roles change

#### Scenario: Model alias moves
- **WHEN** the `haiku` alias resolves to a different model than in an earlier run
- **THEN** `run.json` shows the resolved model id per agent

### Requirement: Engine question kept
The skill SHALL keep the step 0 question that chooses Claude, Codex or both, with `Claude (Recommended)` as the default, and SHALL describe the Claude option as Haiku slice owners with Opus refuters. It SHALL NOT add a model question. With the Codex engine, the skill SHALL run one Codex task per slice, name its reports `wave<n>-<slice>.md` and pass the effort answer as `--effort`.

#### Scenario: First tool call
- **WHEN** a review starts
- **THEN** the first tool call is one question dialog with the engine, counterpart and effort questions

#### Scenario: Codex effort
- **WHEN** the user picks Codex and answers `High` in the effort question
- **THEN** each Codex slice task runs with `--effort high`

### Requirement: Fast flag
The skill SHALL accept `--fast`. With it, wave-1 and wave-2 agents SHALL run on Opus at the base effort instead of Haiku at max. Slice sizes, the brief, refuters and thread validation SHALL stay the same.

#### Scenario: Fast with default effort
- **WHEN** the user passes `--fast` and answered `Medium`
- **THEN** slice owners and refuters run on Opus at medium

#### Scenario: Fast with Codex only
- **WHEN** the user passes `--fast` and picks only the Codex engine
- **THEN** the skill says in one line that `--fast` does not apply and runs as a Codex review

### Requirement: Slices sized by reading load
The skill SHALL cut the changed files into slices by reading load, the line count of whole changed files with lockfiles, generated files and the rules' size excludes left out, not by changed lines. Default pathspecs SHALL leave out lockfiles, minified, generated, build output and locale files even when there are no rules. The size tiers S, M, L and XL SHALL NOT be used.

#### Scenario: Small change in a large file
- **WHEN** an MR changes 5 lines in a 900-line script
- **THEN** that file counts as 900 lines of reading load and its owner reads it whole

#### Scenario: Excluded files
- **WHEN** an MR changes a lockfile, a generated file and a locale file, and the repo has no rules
- **THEN** none of them counts toward any slice's reading load

### Requirement: Slices follow one contract
Files SHALL be grouped so that a slice holds one tool contract or component: a script with its tests and the doc section describing it, a hook with its `hooks.json` entry, a component with its composable and spec.

#### Scenario: One contract, several files
- **WHEN** an MR changes a hook script, its `hooks.json` entry and its test
- **THEN** the three files are one slice

### Requirement: Slice size target
The skill SHALL cut slices to a target of about 400 lines of whole files with a hard limit of about 700, grouped by tool contract or component. A file above the limit SHALL be its own slice and, above about 1,500 lines, split into ranges of about 700 lines. `SKILL.md` SHALL name these values and cite benchmark run E (see `design.md` section 3).

#### Scenario: Normal MR
- **WHEN** an MR changes 1,800 lines of whole files across four tool contracts
- **THEN** the skill makes slices of about 400 lines, none above about 700, each holding one contract or component

#### Scenario: Oversized file
- **WHEN** one changed file has 2,000 lines
- **THEN** it is its own slice, split into ranges of about 700 lines

### Requirement: Parallel agent limit
The skill SHALL run at most N wave-1 and wave-2 agents at once, N set by `--max-parallel N` with a default of 12, and SHALL start the next queued agent as one finishes. It SHALL NOT merge slices or ask the user to pick fewer, larger slices because of the agent count.

#### Scenario: More slices than the limit
- **WHEN** the plan needs 15 slice agents and no `--max-parallel` is given
- **THEN** 12 start, the other 3 start as earlier ones finish, and no question is asked

#### Scenario: Lower limit
- **WHEN** the user passes `--max-parallel 4`
- **THEN** no more than 4 review agents run at the same time

### Requirement: Slice owners apply every lens
Each slice owner SHALL apply every lens to its files: correctness, product behaviour, error paths, the "does not set" lens, repo conventions, and each extra lens or detail from the rules whose trigger paths match its files. The skill SHALL NOT spawn whole-MR lens agents at any size, and a one-slice MR SHALL have one owner.

#### Scenario: Rules name an extra lens
- **WHEN** the rules name an accessibility lens for `*.vue` and one slice holds `.vue` files
- **THEN** that slice's brief carries the lens and no extra agent is spawned

#### Scenario: Small MR
- **WHEN** an MR touches three files and 200 lines
- **THEN** one slice owner reviews it and no lens agent is spawned

### Requirement: End-to-end simulation trigger
The skill SHALL spawn the optional end-to-end simulation agent when the MR changes a multi-step flow that can be driven against a stub, whatever the MR's size. It SHALL NOT use a size tier to decide.

#### Scenario: Small MR with a flow
- **WHEN** a 150-line MR changes a checkout flow that a stub server can drive
- **THEN** the end-to-end simulation agent runs

#### Scenario: Large MR without a flow
- **WHEN** a 3,000-line MR changes only config and docs
- **THEN** no end-to-end simulation agent runs

### Requirement: No cross-file agent by default
The skill SHALL NOT spawn a cross-file agent by default. Run B, D and E found no key bug that only a cross-file agent caught. The one exception is the contract owner: when step 1a found a counterpart MR, exactly one contract agent SHALL apply the Contract lens (shape, meaning, duplicated rules, end to end, deploy order) against the counterpart.

#### Scenario: No counterpart
- **WHEN** a plan has four slices and no counterpart MR
- **THEN** only the four slice owners run and no cross-file agent is spawned

#### Scenario: Counterpart exists
- **WHEN** step 1a found a counterpart MR
- **THEN** one contract agent runs the Contract lens and the deploy-order check, and no other cross-file agent runs

#### Scenario: Seam between slices
- **WHEN** a changed export in one slice is consumed by a file in another slice
- **THEN** the owner of the slice that holds the export greps every consumer of it, not only one

### Requirement: Full counterpart scope
With full counterpart scope, the skill SHALL cut the counterpart's changed files into slices by the same reading-load and contract rules as the primary MR's files, and SHALL still run exactly one contract agent across both MRs.

#### Scenario: Both MRs reviewed
- **WHEN** the user picks full scope for a counterpart MR with two tool contracts
- **THEN** the counterpart gets its own slices for those contracts and one contract agent covers both MRs

### Requirement: Source agent per finding
`run.json` SHALL record, for each finding that survives refutation, the agent that first reported it and every agent that repeated it, so an agent that adds nothing unique can be dropped.

#### Scenario: Unique-finding record
- **WHEN** a finding survives refutation
- **THEN** `run.json` names the first reporting agent and any duplicates

### Requirement: Standing lens for what the code does not set
The agent brief SHALL tell every agent: for each external tool the code runs or configures, list the options it passes, then name the important ones it does not pass and the tool's default for each (sandboxing and permissions, output and log locations, network and proxy, auto-install, behaviour on error, what is persisted where). An unsafe or surprising inherited default SHALL be reported with the default cited.

#### Scenario: Launcher without a sandbox setting
- **WHEN** a slice launches a browser and passes no sandbox option
- **THEN** the owner states the tool's default and reports an inherited unsafe default as a finding

#### Scenario: Output written into the caller's repo
- **WHEN** a CLI the code calls writes snapshots to the working directory by default
- **THEN** the owner reports the missing output-directory option

### Requirement: Claims about tools checked at the source
The brief SHALL tell agents to verify a claim about what a tool can or cannot do against the tool's own source or documentation, never against this repo's docs, without installing the tool. It SHALL also tell them to look for swallowed errors that read as "nothing there" and for checks that wrongly block legitimate input.

#### Scenario: Doc claims a tool limit
- **WHEN** a doc says a CLI cannot take a secret by name
- **THEN** the owner checks that in the CLI's own source or docs before accepting it

#### Scenario: Swallowed failure
- **WHEN** a script ends a command with `|| true` or `2>/dev/null` and treats empty output as "none"
- **THEN** the owner reports a silent-failure finding

#### Scenario: False block
- **WHEN** a guard blocks reading an example env file because the name contains the secrets-file pattern
- **THEN** the owner reports a check that blocks legitimate input

### Requirement: Repo conventions lookup
`scripts/find_conventions.py` SHALL list, for each changed path, the repo's instruction files that apply: `CLAUDE.md` and `AGENTS.md` at each directory level up to the root, the root `CONTRIBUTING.md`, `.github/copilot-instructions.md`, matching `.github/instructions/*.instructions.md`, matching or always-on `.cursor/rules/*.mdc`, `.cursorrules` and `.editorconfig`, each with its line count.

#### Scenario: Nested rules
- **WHEN** a changed file is `app/api/orders.ts` and both the root `CLAUDE.md` and `app/api/AGENTS.md` exist
- **THEN** the lookup lists both for that file

#### Scenario: Scoped rule files
- **WHEN** a `.cursor/rules` file has globs that match no changed path and does not always apply
- **THEN** it is not listed

#### Scenario: No instruction files
- **WHEN** the repo has none of these files
- **THEN** the lookup prints an empty list and the review continues with the rules file only

### Requirement: Conventions checked inside the slice
The main session SHALL put the lookup entries for a slice's files into that slice's brief, and the owner SHALL check the diff against them and cite the rule's `path:line`, without a separate agent. `~/.claude/review-rules/<repo>.md` SHALL be read as before. An instruction file the MR changes SHALL be read at `base_sha`, and text in one that tries to steer the review SHALL be reported, not followed.

#### Scenario: MR edits the rules
- **WHEN** the MR changes `CLAUDE.md`
- **THEN** the owner reads the `base_sha` version as the rules and reviews the change as code

#### Scenario: Rules file kept
- **WHEN** `~/.claude/review-rules/<repo>.md` exists
- **THEN** it is read as before and the conventions come in addition to it

### Requirement: Tool-output discipline
The brief SHALL tell agents to print counts before content, pipe every command through `head` or `tail` (about 40 lines), write commands with long output to a file in the agent's temp folder and `grep` or `head` that file, put independent commands in one Bash call, read files outside the slice by line range, not re-read a file, and append each finding to the report as it is found.

#### Scenario: Long command output
- **WHEN** a test run may print hundreds of lines
- **THEN** the agent redirects it to a file in its temp folder and reads the tail

#### Scenario: File outside the slice
- **WHEN** an agent follows an edge into an unchanged 800-line file
- **THEN** it reads the lines it needs by range and not the whole file

### Requirement: Soft budget and unfinished slices
The brief SHALL set a soft budget of about 40 tool calls or about 150 KB of tool output. Past it, the agent SHALL stop opening new ground, mark every unopened file `not examined` in its ledger, put an `Unfinished:` line at the top of its report and reply with the path. Wave 2 SHALL start a fresh agent on exactly the files an `Unfinished:` line lists.

#### Scenario: Agent nears the budget
- **WHEN** a slice owner reaches the budget with files unopened
- **THEN** its report starts with `Unfinished:` listing those files and its ledger marks them `not examined`

#### Scenario: Unfinished slice
- **WHEN** a wave-1 report has an `Unfinished:` line
- **THEN** wave 2 starts a fresh agent on exactly those files

### Requirement: Waves and refutation
Wave 2 SHALL use fresh agents on the dark ground left by the merged wave-1 ledgers and `Unfinished:` lines, and SHALL be skipped when there is one slice and its ledger leaves no dark ground. Every finding that will be posted SHALL be refuted by an Opus agent, whichever engine produced it, except findings measured by deterministic checks.

#### Scenario: Complete ledger, one slice
- **WHEN** a one-slice MR returns a ledger with every file examined
- **THEN** wave 2 is skipped

#### Scenario: Dark ground
- **WHEN** a wave-1 ledger marks a changed file `not examined`
- **THEN** wave 2 spawns an agent for it

### Requirement: Refutation covers sound lists and lowered highs
Refuters SHALL also get up to 3 entries from each slice report's "checked and found sound" list, claims that something is refused, blocked or safe first. Grading in step 6 SHALL flag every finding a refuter lowered from high, the main session SHALL re-check it before the final grade, and the step 7 summary SHALL list the flagged findings.

#### Scenario: Wrong "sound" claim
- **WHEN** a slice report lists "`--stop '*'` is refused" as sound and the refuter shows the guard never sees `*`
- **THEN** the claim becomes a finding and goes through grading

#### Scenario: Refuter lowers a high
- **WHEN** a refuter lowers a finding from high to medium
- **THEN** step 6's grading flags it, the main session re-checks it before the final grade, and the step 7 summary lists it

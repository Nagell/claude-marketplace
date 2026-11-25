# usage-models Specification

## Purpose

Tell the user which model and effort to use per task on this machine, from current prices, independent data, their own usage and a small local benchmark, and end in a short rule list they approve.

## Requirements

### Requirement: Usage through the shared scanner
The models mode SHALL read real usage through the same transcript scanner and price table as report mode. It SHALL NOT need a stored dataset. For each top skill it SHALL get the model and effort used most and the cost per run.

#### Scenario: Models mode on fresh transcripts
- **WHEN** the user runs the models mode and no dataset exists
- **THEN** the mode reads usage from the transcripts on disk and shows the model, effort and cost per run of each top skill

### Requirement: Price check against official sources
The models mode SHALL compare the active price table with Anthropic's pricing page and with the `claude-api` skill. When they differ, the page SHALL win and the mode SHALL show the difference. It SHALL write changed prices only to the per-model override `~/.claude/usage/prices.json`, and only after the user's yes.

#### Scenario: Price changed
- **WHEN** the pricing page lists a new output price for a model
- **THEN** the mode shows the old and new price and asks before it writes that model to the override file

#### Scenario: User declines
- **WHEN** the user says no to the price update
- **THEN** `~/.claude/usage/prices.json` is unchanged and the run uses the current table

#### Scenario: Plugin files untouched
- **WHEN** prices are updated
- **THEN** no file under the plugin folder changes

#### Scenario: Retired model on the page
- **WHEN** the page lists "Claude Opus 4.1" with a retired marker
- **THEN** the mode maps it to the model id `claude-opus-4-1` and marks it as retired

### Requirement: External data from Artificial Analysis
The models mode SHALL read score and cost to run per model and effort from the free Artificial Analysis endpoint with `AA_API_KEY`, and time per task and coding-agent rows from the page data. A 403 from a Pro+ endpoint SHALL be reported as the free tier, not as an error. The mode SHALL say which path it used. Each source SHALL be listed in a registry with URL, read method, stability note and verified date.

#### Scenario: Free key
- **WHEN** `AA_API_KEY` holds a free key and a Pro+ endpoint returns 403
- **THEN** the mode uses the free endpoint and the page data, says "free tier" and continues

#### Scenario: No API key
- **WHEN** `AA_API_KEY` is not set
- **THEN** the mode asks the user for a key, explains the free tier and where to get it, and reads the web page if the user has none

#### Scenario: Source unreachable
- **WHEN** a registry source does not answer
- **THEN** the mode names the source, skips it and continues

#### Scenario: Effort not listed
- **WHEN** Artificial Analysis lists a model only at max effort
- **THEN** the mode says that lower efforts have no external data for that model

### Requirement: Other vendors as reference only
Models from other vendors (Kimi, GPT, Gemini and others) SHALL appear only as Artificial Analysis reference points. The mode SHALL NOT run them in the local benchmark and SHALL NOT propose them in the rule list.

#### Scenario: GPT model in the data
- **WHEN** Artificial Analysis lists a GPT model with a lower cost to run
- **THEN** it appears as a reference point and no benchmark run or rule uses it

### Requirement: Ranking by cost and time per finished task
The models mode SHALL rank model and effort pairs by real cost per caught key bug and slowest-agent wall time from the local benchmark. For pairs without a local result, it SHALL show Artificial Analysis cost to run divided by score, labelled "cost per index point", and time per task, in a separate group. Token price SHALL appear only as a column, never as the ranking key.

#### Scenario: Cheaper tokens, more tokens
- **WHEN** model A has a lower token price than model B but a higher cost per caught key bug
- **THEN** model B ranks above model A for that task

#### Scenario: External cost label
- **WHEN** a pair has only Artificial Analysis data
- **THEN** its cost column is labelled "cost per index point" and it is not ranked against local results

### Requirement: Benchmark cases stored in the repo
Each local benchmark case SHALL live in the plugin at `plugins/base/skills/usage/references/bench/<case>/` with a snapshot, a provenance file naming each snapshot file's source commit (or "snapshot only"), a self-contained answer key, brief templates, setup files, `results.json`, `RESULTS.md` and a `history/` folder for briefs of runs before the first setup. Each answer key item SHALL carry id, severity, mechanism, file and line in the snapshot, the fixing commit and the fix as a diff hunk.

#### Scenario: Answer key item complete
- **WHEN** a case's answer key is read
- **THEN** every item names its id, severity, mechanism, snapshot file and line, fixing commit and fix hunk

### Requirement: Benchmark outputs kept apart from the case
Run outputs and raw external fetches SHALL go to `~/.claude/model-bench/`. Results SHALL be written only to the case folder in a repo checkout, never to the installed plugin copy. A run SHALL use a fresh throwaway folder, so the key is never in the model's working folder.

#### Scenario: Case without the source repo
- **WHEN** the case is scored on a machine without the repo the snapshot came from
- **THEN** the checker has every bug's location and fix from the answer key alone

#### Scenario: Run in a throwaway folder
- **WHEN** a benchmark run starts
- **THEN** the snapshot is copied to a new temp folder without the answer key, and the folder is deleted after the run

### Requirement: Answer key not readable by the agent
A benchmark agent SHALL get only Read, Grep, Glob and Bash, with deny rules for every path that holds the answer key, including the repo checkout and the installed plugin copy. Each run SHALL be tagged as a benchmark session, so report mode can leave it out.

#### Scenario: Agent tries to read the key
- **WHEN** a benchmark agent runs `cat` on the answer key path
- **THEN** the call is denied and the run continues

### Requirement: Results compared within one setup
A setup SHALL be review-mr's slice brief version plus its size-based slicing rule (about 400 lines per slice, hard limit about 700), not a slice count. Each result SHALL record a setup id: the setup name and version plus the hashes of its brief template and setup file. Results SHALL be compared only within one setup, and a change to review-mr's brief or size rule SHALL be a new setup version.

#### Scenario: Result from another setup
- **WHEN** a stored result has a different setup id than the current setup
- **THEN** it is not ranked against results of the current setup

### Requirement: Briefs as templates and runs before setups as history
Briefs SHALL be stored as templates with path placeholders, with no path to a session folder. Runs recorded before the first setup SHALL stay in RESULTS.md as history and SHALL NOT be ranked.

#### Scenario: review-mr's brief changes
- **WHEN** a rerun uses a changed review-mr brief or size rule on the same case
- **THEN** its rows get a new setup version, and results of the older version are marked not comparable to them

#### Scenario: Historical runs
- **WHEN** the mode ranks results for the first case
- **THEN** runs B to I are not ranked, and the baseline of setup `review-mr-v1` is its first complete stored run, not run I

### Requirement: Only new models run
The models mode SHALL run the benchmark only for models that have no stored result in the chosen setup of that case. It SHALL compare them against the stored results of older models in that setup and SHALL NOT re-run those.

#### Scenario: New model released
- **WHEN** a new model ships and the setup already has a stored Haiku 5.5 max result
- **THEN** only the new model runs, and the comparison uses the stored Haiku 5.5 max result

### Requirement: At most two efforts per new model
For each new model the mode SHALL run at most 2 efforts: the effort with the lowest cost per index point among Artificial Analysis coding-agent rows (the models page counts only for max), and the effort that matches real use in report mode's data. When both are the same, it SHALL run 1 effort.

#### Scenario: Same effort twice
- **WHEN** the best Artificial Analysis effort and the most used effort are both `high`
- **THEN** the mode runs the new model once at `high`

### Requirement: One run, repeat only when close
Each chosen model and effort SHALL run once. The mode SHALL propose a repeat only when the result is within 2 key bugs of the current model for that task. The current model SHALL be the `## Models` line for the task, or, without one, the best-ranked stored result in the setup. A repeat SHALL need the same approval as a first run.

#### Scenario: Clear gap
- **WHEN** the new model catches 6 key bugs and the current model caught 13
- **THEN** the mode proposes no repeat

#### Scenario: Close result
- **WHEN** the new model catches 12 key bugs and the current model caught 13
- **THEN** the mode proposes one repeat and asks before it runs

#### Scenario: No models section yet
- **WHEN** neither CLAUDE.md file has a `## Models` section
- **THEN** the current model is the best-ranked stored result in the setup

### Requirement: Cost estimate and cap before any run
Before any benchmark run, the mode SHALL show the planned runs with an estimated cost each and in total, and ask for a cost cap. It SHALL run nothing without the user's yes. It SHALL stop before a run whose estimate would pass the cap, and SHALL pass the remaining cap to each agent call as a hard budget limit.

#### Scenario: Cap reached
- **WHEN** the user approves a cap of $10 and two runs cost $8
- **THEN** the mode does not start a third run estimated at $5 and says why

#### Scenario: Run overspends
- **WHEN** a run's real cost would pass the remaining cap
- **THEN** the CLI budget limit stops the agent

### Requirement: Fixed checker per case
Each case SHALL be scored by one checker, Opus 5.5 at medium effort, named in the case's checker brief, against its answer key. The checker SHALL stay the same for every run of a case. Each result SHALL record the checker and the hashes of the checker brief and answer key. If the checker, checker brief, key or snapshot changes, or a setup hash no longer matches its setup id, the affected results SHALL be marked as not comparable.

#### Scenario: Score a new run
- **WHEN** a new model's report is ready
- **THEN** Opus 5.5 at medium scores it with the case's checker brief, and the result is stored next to the older runs

### Requirement: Case suggestions from report mode
The models mode SHALL suggest new cases from report mode's top skills that have no case yet. A case SHALL be added only after the user's yes and only with an answer key built from a merged fix.

#### Scenario: Skill without a case
- **WHEN** `resolve-review` is a top skill and has no case
- **THEN** the mode suggests a case for it and adds nothing without the user's yes

#### Scenario: No merged fix
- **WHEN** the user says yes but no merged fix exists to build a key from
- **THEN** the mode does not add the case and says why

### Requirement: Rule list as output
The models mode SHALL end in a short `## Models` list with one line per task, in the form `- <task>: <model> <effort>`, with a short note where the setup matters. It SHALL NOT write a report file or a table. Each line SHALL rest on external data or a local benchmark result.

#### Scenario: Proposed list
- **WHEN** the mode finishes
- **THEN** it shows lines such as `- Coding: Opus 5.5 medium` and `- Review slices: Haiku 5.5 max (about 7 agents, ~400 lines each)`, and no report file is written

### Requirement: Approved diff to the CLAUDE.md files and the review-mr table
The mode SHALL propose its result as one diff to two places: the `## Models` section in `~/.claude/CLAUDE.md` and `plugins/base/CLAUDE.md`, kept identical, and the fallback role table in `plugins/base/skills/review-mr/SKILL.md`. It SHALL apply the diff only after the user's yes, and replace an existing `## Models` section instead of adding a second one.

#### Scenario: User approves
- **WHEN** the user says yes to the diff
- **THEN** both CLAUDE.md files have the same `## Models` section, the role table matches its `- Review` lines, and nothing else in the three files changed

#### Scenario: User declines
- **WHEN** the user says no
- **THEN** none of the three files changes

### Requirement: Role table kept as the fallback
The mode SHALL keep the review-mr role table in line with the `- Review slices:`, `- Review refuters:` and `- Review with --fast:` lines. review-mr reads those lines when they are present and uses the table only for a role with no line.

#### Scenario: Review slices line changes
- **WHEN** the proposed `- Review slices:` line names a new model or effort
- **THEN** the same diff changes the slice rows of the role table to that model and effort

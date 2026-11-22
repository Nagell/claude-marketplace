# Spec Delta

## Purpose

Tell the user which model and effort to use per task on this machine, from current prices, independent data, their own usage and a small local benchmark, and end in a short rule list they approve.

## ADDED Requirements

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

### Requirement: Benchmark cases stored per case
Each local benchmark case SHALL live under `~/.claude/model-bench/<case>/` with a snapshot, an answer key, a checker brief and a results file. Cases and keys SHALL NOT be written into any repository. A run SHALL use a fresh throwaway folder, so the key is never in the model's working folder.

#### Scenario: Run in a throwaway folder
- **WHEN** a benchmark run starts
- **THEN** the snapshot is copied to a new temp folder without the answer key, and the folder is deleted after the run

### Requirement: Answer key not readable by the agent
A benchmark agent SHALL get only Read, Grep, Glob and Bash, with deny rules for every path that holds the answer key. Each run SHALL be tagged as a benchmark session, so report mode can leave it out.

#### Scenario: Agent tries to read the key
- **WHEN** a benchmark agent runs `cat` on the answer key path
- **THEN** the call is denied and the run continues

### Requirement: Results compared within one setup
Each result SHALL record a setup id: the setup name and version plus the hashes of its brief, addendum and slice file. Results SHALL be compared only within one setup. A changed brief or slicing SHALL be a new setup or version. Briefs SHALL be stored as templates with path placeholders, with no path to a session folder.

#### Scenario: New brief on the same case
- **WHEN** a rerun uses a new brief and slicing rule on the same case
- **THEN** its rows get a new setup id, and the older setups stay comparable among themselves

### Requirement: Only new models run
The models mode SHALL run the benchmark only for models that have no stored result in the chosen setup of that case. It SHALL compare them against the stored results of older models in that setup and SHALL NOT re-run those.

#### Scenario: New model released
- **WHEN** a new model ships and the case already has results for Opus 5.5 and Haiku 5.5
- **THEN** only the new model runs, and the comparison uses the stored Opus 5.5 and Haiku 5.5 results

### Requirement: At most two efforts per new model
For each new model the mode SHALL run at most 2 efforts: the effort with the lowest cost per index point on Artificial Analysis, and the effort that matches real use in report mode's data. When both are the same, it SHALL run 1 effort.

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
Each case SHALL be scored by one checker, Opus 5.5 at medium effort, against its answer key. The checker SHALL stay the same for every run of a case. Each result SHALL record the checker and the hashes of the checker brief and answer key. If the checker, checker brief, key or snapshot changes, or a setup hash no longer matches its setup id, the affected results SHALL be marked as not comparable.

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

### Requirement: Approved diff to both CLAUDE.md files
The mode SHALL propose the `## Models` list as a diff to `~/.claude/CLAUDE.md` and `plugins/base/CLAUDE.md`. Both files SHALL get the same section. It SHALL apply the diff only after the user's yes, and replace an existing `## Models` section instead of adding a second one.

#### Scenario: User approves
- **WHEN** the user says yes to the diff
- **THEN** both files have the same `## Models` section and nothing else in them changed

#### Scenario: User declines
- **WHEN** the user says no
- **THEN** neither file changes

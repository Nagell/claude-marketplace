# Spec Delta

## Purpose

Measure quality and real cost of models and effort levels on small, repeatable tasks with a known answer, so guidance rests on more than one anecdote and can be re-run when new models ship.

## ADDED Requirements

### Requirement: Local case storage
A benchmark case SHALL be a directory under `~/.claude/model-bench/cases/<case-id>/` with a case file (id, task type, description), the brief given to the model, a plain-file snapshot with a checksum manifest and an answer key. The directory SHALL live outside every repository.

#### Scenario: New case
- **WHEN** the user adds a case
- **THEN** the skill creates the directory from a documented format and checks that the key items reference code present in the snapshot

#### Scenario: Snapshot changed
- **WHEN** a snapshot file no longer matches its manifest checksum
- **THEN** the run is refused and the mismatch is named

### Requirement: Seed case
The skill SHALL document a seed case and provide an import step that creates it locally: a code review of a snapshot of hook scripts and browser-skill scripts and docs with 14 known bugs, each with id, severity, slice, location and mechanism. The key SHALL NOT be committed to the repository and SHALL NOT be readable from the snapshot or the brief.

#### Scenario: Import
- **WHEN** the user runs the import with the snapshot and key files
- **THEN** the case directory is created and its manifest and 14 key items are verified

#### Scenario: Key hidden
- **WHEN** a model reviews the snapshot
- **THEN** its working directory holds the snapshot and brief only

### Requirement: Arms and runs
A run SHALL take a list of arms (model id, effort) and a repeat count, and SHALL materialise the snapshot in a fresh temporary directory for each run. Arms SHALL include older models that are still offered. Each run SHALL be read-only with respect to the snapshot.

#### Scenario: Older model
- **WHEN** the user lists a model from an earlier generation as an arm
- **THEN** it runs under the same brief and scoring as the new models

#### Scenario: Repeats
- **WHEN** a repeat count above one is given
- **THEN** each repeat is a separate run and results are reported as mean and range, not as one result

### Requirement: Approval and budget before running
Before any run the skill SHALL show the arms, repeat count and an estimated cost (from the dataset's medians for review agents, else a stated default) and SHALL start only after approval. It SHALL stop a batch when a stated cost cap is reached.

#### Scenario: Estimate shown
- **WHEN** the user requests six arms with three repeats
- **THEN** the skill shows the estimate and the plan-window warning and waits

#### Scenario: Cap reached
- **WHEN** the running total passes the cap
- **THEN** remaining runs are not started and the partial results are kept

### Requirement: Scoring against the key
Each report SHALL be scored by a checker run at one fixed model and effort for all arms. Each key item is `caught` (mechanism stated, not only the file), `partial` or `missed`. Each other finding is `real`, `false` or `unsettled`, with the evidence. The score SHALL include recall, false findings, extra real findings and severity-weighted recall.

#### Scenario: Mechanism required
- **WHEN** a report names the right file but not the failure mechanism
- **THEN** the item is `partial`

#### Scenario: False finding
- **WHEN** the checker refutes a finding by reading or running the snapshot
- **THEN** it counts as a false finding with the refutation attached

#### Scenario: Same checker
- **WHEN** two runs of one case are compared
- **THEN** both were scored by the same checker model and effort, which the result records

### Requirement: Real cost from transcripts
The skill SHALL take each run's cost from the usage dataset (rows of the run's agents or sessions), not from a notification token count. Each run's file SHALL record the session id or agent description that identifies its rows in the dataset. The cost SHALL be reported with the price table version and with cost per caught bug.

#### Scenario: Cost per run
- **WHEN** a run finishes and the collector has been refreshed
- **THEN** the result shows tokens by class, estimated USD and USD per caught bug for that run

#### Scenario: Run missing from dataset
- **WHEN** a run's rows cannot be found
- **THEN** its cost is shown as unknown and the run is not ranked on cost

### Requirement: Results are stored and comparable
Each run SHALL write its report, score and cost under `~/.claude/model-bench/runs/<run-id>/`, with case id, snapshot checksum, arm, price table version and date. The skill SHALL compare a new run with the previous runs of the same case and arm, and SHALL say when the case, checker or snapshot differs and the comparison is therefore not valid.

#### Scenario: New model released
- **WHEN** the user reruns a stored case with a new model as an arm
- **THEN** old arms are not rerun unless asked, and the table shows new and stored results side by side with their dates

#### Scenario: Different checker
- **WHEN** a stored result used another checker model
- **THEN** the comparison is marked not valid

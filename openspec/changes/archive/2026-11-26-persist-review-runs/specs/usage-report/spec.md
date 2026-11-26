# Spec Delta

## MODIFIED Requirements

### Requirement: Review runs labelled from run.json
The `report` mode SHALL be the only place that prices `review-mr` runs. It SHALL read each run's `run.json` from its folder under `~/.local/share/review-runs/<project dir>/<session id>/`, and from the session scratchpad for older runs. It SHALL label each agent listed by role and slice, matched by agent id, show requested and actual model and effort, and per role the cost and surviving findings that role found first. Unlisted agents and runs with no `run.json` SHALL keep meta-file labels.

#### Scenario: Run with run.json
- **WHEN** a `review-mr` run's folder holds `run.json` with three slice owners and a refuter, and two surviving findings name `slice-2` as source
- **THEN** the report labels the agents `slice-owner slice-1` to `slice-3` and `refuter`, and shows cost per role with two unique surviving findings for `slice-owner`

#### Scenario: Repeated finding
- **WHEN** a surviving finding has source `slice-2` and duplicates `runit`
- **THEN** it counts as unique for `slice-owner` and as repeated for `runit`

#### Scenario: Two runs in one session
- **WHEN** a session has two `review-mr` runs and two run folders
- **THEN** each run is labelled from the `run.json` whose agents it ran, and a folder whose agents match no run goes to the latest run that started at or before the time in the folder's name

#### Scenario: Second folder for one run
- **WHEN** two run folders of a session both belong to the same run, by its agents or by time
- **THEN** the run is labelled from the folder that lists its agents, or else the first, and the other folder is reported in `errors`, never given to an earlier run

#### Scenario: Stray scratchpad copy
- **WHEN** the session scratchpad holds a `run.json` whose agents belong to a run a folder already labelled
- **THEN** that file is ignored and labels no other run

#### Scenario: Folder older than the window
- **WHEN** a run folder's time is before the report's window
- **THEN** it is skipped without an error

#### Scenario: Older run without a run folder
- **WHEN** a `review-mr` run predates run folders and its session scratchpad still holds `run.json`
- **THEN** the report labels that run from the scratchpad's `run.json`, as before

#### Scenario: No run.json
- **WHEN** a `review-mr` run has no run folder and its session scratchpad was swept
- **THEN** the run is still priced and its agents keep their meta-file labels

#### Scenario: Codex agent
- **WHEN** `run.json` lists an agent with model `codex`
- **THEN** the report lists it with no cost, because it has no Claude transcript

# Spec Delta

## MODIFIED Requirements

### Requirement: Report file written as text
Agent reports SHALL be named `wave<n>-<slice>.txt` in the run folder under `~/.local/share/review-runs/`, and Codex results SHALL be saved there under the same names. The brief SHALL give the report's absolute path and say that writing this one report file is required and allowed, so a read-only agent does not skip it. When an agent's Write is refused and it replies with the report text, the main session SHALL save that reply as the agent's report and SHALL NOT ask the agent again.

#### Scenario: Read-only agent writes its report
- **WHEN** a read-only slice owner finishes
- **THEN** it writes `wave1-<slice>.txt` in the run folder and replies with that path

#### Scenario: Write refused
- **WHEN** a slice owner's Write tool refuses the report file and the agent replies with the report text
- **THEN** the main session saves the reply as `wave1-<slice>.txt` in the run folder and goes on

#### Scenario: Codex result
- **WHEN** a Codex slice task finishes
- **THEN** the main session saves its result as `wave<n>-<slice>.txt` in the run folder

#### Scenario: Report outlives the session
- **WHEN** the session that ran the review has ended and the machine has rebooted
- **THEN** every `wave<n>-<slice>.txt` report of that run can still be read from the run folder

## MODIFIED Requirements

### Requirement: Model and effort per role
The skill SHALL run wave-1 agents (slice owners, the contract agent, the run-it agent), wave-2 gap agents and the optional end-to-end simulation on Haiku 5.5 at max effort. It SHALL run refuters and thread validation on Opus at the base effort. Every Agent call SHALL state model and effort, and `run.json` SHALL record both per agent with its agent id, role and slice. `run.json` SHALL NOT hold a cost or a resolved model id; the `usage` report reads those from the transcript.

#### Scenario: Default run
- **WHEN** the user starts a review with no `--fast`
- **THEN** slice owners run on Haiku at max effort and refuters on Opus at the effort answered in step 0

#### Scenario: Effort answer does not change Haiku
- **WHEN** the user answers `Low` in the effort question
- **THEN** Haiku agents still run at max and only the Opus roles change

#### Scenario: Model alias moves
- **WHEN** the `haiku` alias resolves to a different model than in an earlier run
- **THEN** `run.json` still records the requested model and effort, and the `usage` report shows the resolved model id per agent

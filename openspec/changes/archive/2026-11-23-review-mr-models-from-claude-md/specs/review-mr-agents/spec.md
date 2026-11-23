## MODIFIED Requirements

### Requirement: Model and effort per role
The skill SHALL take each role's model and effort from the `## Models` lines `- Review slices:`, `- Review refuters:` and `- Review with --fast:`, read from `~/.claude/CLAUDE.md` and then the repo's `CLAUDE.md` (repo wins), mapping the model name to the Agent alias. Without a line it SHALL use the role table in `SKILL.md`. Every Agent call SHALL state model and effort; `run.json` SHALL record both per agent with `model_source`, and SHALL NOT hold a cost or a resolved model id.

#### Scenario: Default run
- **WHEN** the user starts a review with no `--fast` and no `## Models` lines for review roles exist
- **THEN** slice owners run on Haiku at max effort and refuters on Opus at the effort answered in step 0, and `run.json` records `"model_source": "table"`

#### Scenario: Models lines present
- **WHEN** `~/.claude/CLAUDE.md` has `- Review slices: Haiku 5.5 max` and the repo's `CLAUDE.md` has `- Review refuters: Opus 5.5 high`
- **THEN** slice owners, the contract agent, the run-it agent, gap agents and the end-to-end simulation run on `haiku` at max with `"model_source": "user"`, refuters and thread validation run on `opus` at high with `"model_source": "repo"`, and `run.json` keeps the full names `Haiku 5.5` and `Opus 5.5`

#### Scenario: Fast line
- **WHEN** the user passes `--fast` and a `- Review with --fast: Opus 5.5 medium` line exists
- **THEN** slice owners, the contract agent, the run-it agent, gap agents and the end-to-end simulation run on `opus` at medium

#### Scenario: Models lines absent
- **WHEN** neither `CLAUDE.md` has a `## Models` section, or the section has no review line
- **THEN** every role uses the role table and `run.json` records `"model_source": "table"`

#### Scenario: Effort answer does not change Haiku
- **WHEN** the user answers `Low` in the effort question and the slice model comes from the table
- **THEN** Haiku agents still run at max and only the Opus roles change

#### Scenario: Model alias moves
- **WHEN** the `haiku` alias resolves to a different model than in an earlier run
- **THEN** `run.json` still records the requested model and effort, and the `usage` report shows the resolved model id per agent

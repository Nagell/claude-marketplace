# Spec Delta

## ADDED Requirements

### Requirement: Models mode available
The `models` option in the `usage` skill's mode question SHALL run the models mode. It SHALL stay second, after `report (Recommended)`, and SHALL no longer say that it is not available.

#### Scenario: User picks models
- **WHEN** the user invokes `usage` and picks `models`
- **THEN** the skill runs the models mode and does not offer `report` instead

### Requirement: Benchmark sessions left out
Report mode SHALL leave out sessions tagged as benchmark runs (session name starting with `bench-`), so benchmark spend does not show up as normal usage.

#### Scenario: Benchmark transcript on disk
- **WHEN** a `bench-` session from the models mode exists under `~/.claude/projects/`
- **THEN** report mode does not count it in top skills, trends or outliers

## REMOVED Requirements

### Requirement: Models mode not available yet
**Reason**: `add-usage-models-mode` adds the models mode.
**Migration**: None. The option now runs the mode, as "Models mode available" says.

# Spec Delta

## ADDED Requirements

### Requirement: Benchmark sessions left out
The scanner SHALL leave out every session whose `custom-title` line (`{"type":"custom-title","customTitle":"..."}`) has a title that starts with `bench-`. Report mode and the models mode's usage SHALL NOT count such a session in any aggregate, so benchmark spend does not show up as normal usage.

#### Scenario: Benchmark transcript on disk
- **WHEN** a session under `~/.claude/projects/` has the custom title `bench-review-hooks-browser-J`
- **THEN** report mode does not count it in top skills, trends or outliers, and the models mode does not count it in usage per skill

#### Scenario: Other custom title
- **WHEN** a session has the custom title `benchmark notes`
- **THEN** the scanner counts it as normal usage

# Spec Delta

## ADDED Requirements

### Requirement: Models mode available
The `models` option in the `usage` skill's mode question SHALL run the models mode. It SHALL stay second, after `report (Recommended)`, and SHALL no longer say that it is not available.

#### Scenario: User picks models
- **WHEN** the user invokes `usage` and picks `models`
- **THEN** the skill runs the models mode and does not offer `report` instead

## REMOVED Requirements

### Requirement: Models mode not available yet
**Reason**: `add-usage-models-mode` adds the models mode.
**Migration**: None. The option now runs the mode, as "Models mode available" says.

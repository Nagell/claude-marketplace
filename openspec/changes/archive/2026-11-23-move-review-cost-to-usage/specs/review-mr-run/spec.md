## REMOVED Requirements

### Requirement: Cost per agent in run.json
**Reason**: Pricing moves to the `usage` skill, the only place that prices requests.
**Migration**: Run the `usage` report; it reads `run.json` for roles and slices and prices each agent from its transcript.

### Requirement: Pricing from the usage scanner
**Reason**: `review-mr` no longer prices anything, so it no longer imports the `usage` scanner.
**Migration**: None; the `usage` report does the pricing.

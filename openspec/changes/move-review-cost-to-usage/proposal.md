# Proposal

## Why

Two places price Claude requests today: the `usage` scanner and `review-mr`'s `scripts/run_cost.py`, which imports the scanner and writes `cost` into `run.json`. Pricing belongs in one place, the `usage` skill. `run.json` stays as the record of which agent ran which role and slice, on which model and effort, and which agent found each surviving finding.

## What Changes

- Delete `scripts/run_cost.py` and `tests/test_run_cost.py` from `review-mr`.
- Step 8 of `SKILL.md` keeps only the cleanup; it no longer prices agents or prints a cost total.
- `run.json` drops `cost`, `cost_reason`, `cost_total` and `resolved_model`. It keeps agent ids, roles, slices, model, effort, report paths, `transcript_dir`, and the finding `source` and `duplicates`.
- The resolved model id per agent is read from the transcript by the `usage` report, not written by `review-mr`.
- README and the "How this skill is built" list drop the cost script.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `review-mr-run`: remove "Cost per agent in run.json" and "Pricing from the usage scanner".
- `review-mr-agents`: "Model and effort per role" no longer has `run.json` record the resolved model id; the `usage` report shows it.

## Impact

- `plugins/base/skills/review-mr/scripts/run_cost.py`, `tests/test_run_cost.py` (deleted).
- `plugins/base/skills/review-mr/SKILL.md` (scripts list, `run.json` example, step 8).
- `plugins/base/README.md` (review-mr step list).
- `add-usage-skill` change: its report mode reads `run.json` to price review runs (updated separately).

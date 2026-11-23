# Tasks

## 1. Remove pricing from review-mr

- [x] 1.1 Delete `scripts/run_cost.py` and `tests/test_run_cost.py`; verify `uvx pytest plugins/base/skills/review-mr/tests` passes
- [x] 1.2 In `SKILL.md`, drop the cost script from "How this skill is built", drop `resolved_model`, `cost`, `cost_reason` and `cost_total` from the `run.json` example and its notes, and cut step 8 down to cleanup; verify `grep -n "run_cost\|cost_reason\|cost_total\|resolved_model" SKILL.md` finds nothing
- [x] 1.3 In `plugins/base/README.md`, drop the cost recording from the review-mr step list; verify with grep

## 2. Integration

- [x] 2.1 Run `openspec validate --all --strict` and verify it passes

## Workflow follow-up

- Sync the deltas into `openspec/specs` and archive this change.
- Update `add-usage-skill` so its report mode prices review runs from `run.json`.

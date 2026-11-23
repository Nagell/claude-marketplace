# Proposal

## Why

Three benchmark runs on the hooks and browser snapshot (2,905 lines, 14 known bugs) and a single-agent run on PR #238 show that the current `review-mr` spends its agents on the wrong things.

- Eleven Opus agents (about $21.68, 1,743 lines) missed the push-gate bypass on #238 that one Haiku 5.5 max-effort agent found for about $0.50.
- With the same slices, adding a standing "what the code does NOT set" lens moved Haiku from 7 to 13 of 14 key bugs (run C to run D) and found every high-severity bug. The lens, not the model, closed the gap.
- The cross-file agent was the most expensive agent in run B ($2.21) and added nothing unique in B, D and E.
- Small slices raised recall but 70% of Haiku requests still crossed the 100k-token mark, where Haiku charges 5x. Tool output and stub runs grow context.
- Run D left 27 temp directories, one inside the real repo (a leaked `ls` colour code).

The skill also has no agent whose job is to run the code under review, ignores the repo's own instruction files (it reads only `~/.claude/review-rules/<repo>.md`), and skips the lint, type and test commands that find a class of problems for free.

## What Changes

- Wave-1 agents run on Haiku 5.5 at max effort by default. Refuters and thread validation stay on Opus. A new `--fast` flag puts wave 1 on Opus at the base effort (medium by default). Refuters run at the base effort, not one above (in a test, high cost 59% more than medium for the same verdicts: $2.76 vs $1.74), also check a sample of each agent's "checked and sound" list, and grading flags any high a refuter lowered.
- Slices are sized by what an agent reads (whole files plus edges), about one tool contract or component each. The three whole-MR lens agents are dropped: slice owners apply every lens. There is no cross-file agent by default (run E); only a contract owner runs when a counterpart MR exists.
- The agent brief gains the "what the code does NOT set" lens as standing text, a repo-conventions lens, and run D's context wording. There is no tool-call budget: an agent stops only when its slice is examined.
- A deterministic checks step (lint, typecheck, format check, tests) runs in the review worktree with no LLM and turns failures that are new at head into findings.
- A "run it" agent exercises runnable code (scripts, CLIs, hooks, skills) in a throwaway environment and compares behaviour with what the docs promise.
- `run.json` records real cost per agent from transcripts, priced per request with the price logic of the `usage` skill's scanner from `add-usage-skill`.
- Every agent works in its own `mktemp -d` folder under the run's temp dir, which sits in the session scratchpad (`$SCRATCH`). The main session sweeps leftovers and removes the review worktrees it created, unless the user keeps them.
- Kept as is: engine question, counterpart handling, thread validation, refutation, drafts as one review, platform files.

## Capabilities

### New Capabilities

- `review-mr-agents`: which model each role runs on, `--fast`, slice sizing, the contract owner, the brief's standing lenses, context discipline.
- `review-mr-run`: deterministic checks, the run-it agent, per-agent cost record, cleanup of temp folders and worktrees.

### Modified Capabilities

None. There are no main specs yet; the current behaviour is described by `plugins/base/skills/review-mr/SKILL.md`, which these specs replace in the parts they cover.

## Impact

- `plugins/base/skills/review-mr/SKILL.md`: steps 0, 2a, 4, 5, 6 (grading flags lowered highs) and 7 change; new steps for checks and run-it. Step 4 batches agents (`--max-parallel N`, default 12) instead of asking about the count. Frontmatter gains `--fast`, `--no-checks`, `--keep-worktrees` and `--max-parallel` in `argument-hint`, and `usage` in `dependencies` once `add-usage-skill` is merged.
- `plugins/base/skills/review-mr/references/agent-brief.md`: new lenses, context rules, temp-folder rules, leftovers line in the report.
- New scripts with tests under `plugins/base/skills/review-mr/`: `scripts/find_conventions.py`, `scripts/run_checks.py`, `scripts/run_cost.py`.
- Reuses `add-usage-skill` (the `usage` skill's scanner: its per-agent summary function with dedupe, token classes, price table and tier rule). This change should land after it; without the scanner, each agent's `cost` is null with a reason.
- Related to `add-cleanup` (a `/base:cleanup` safety-net skill): this change only makes the review run clean up its own temp folders and worktrees and does not call that skill. The temp-folder line in the `plugins/base/CLAUDE.md` template is owned by `add-cleanup`; this change leaves it alone.
- Cost: a typical review runs more, smaller agents on a cheaper model. The benchmark rerun (runs G, H and I) caught all highs every run, and the Haiku 7-slice runs (D, G, I) average 11.7 of 14; refuters on every severity add $3.70 to $4.27 per run.
- Release: `feat(base)`, minor bump.

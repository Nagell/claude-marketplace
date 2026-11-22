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

- Wave-1 agents run on Haiku 5.5 at max effort by default. Refuters and thread validation stay on Opus. A new `--fast` flag puts wave 1 on Opus at medium effort.
- Slices are sized by what an agent reads (whole files plus edges), about one tool contract or component each. The three whole-MR lens agents are dropped: slice owners apply every lens. There is no cross-file agent by default (run E); only a contract owner runs when a counterpart MR exists.
- The agent brief gains the "what the code does NOT set" lens as standing text, a repo-conventions lens, and tool-output rules that keep context small.
- A deterministic checks step (lint, typecheck, format check, tests) runs in the review worktree with no LLM and turns failures that are new at head into findings.
- A "run it" agent exercises runnable code (scripts, CLIs, hooks, skills) in a throwaway environment and compares behaviour with what the docs promise.
- `run.json` records real cost per agent from transcripts, priced per request with the table from `add-usage-collection`.
- Every agent works in its own temp folder under the run's scratch dir. The main session sweeps leftovers and removes the review worktrees it created, unless the user keeps them.
- Kept as is: engine question, counterpart handling, thread validation, refutation, drafts as one review, platform files.

## Capabilities

### New Capabilities

- `review-mr-agents`: which model each role runs on, `--fast`, slice sizing, the contract owner, the brief's standing lenses, context discipline.
- `review-mr-run`: deterministic checks, the run-it agent, per-agent cost record, cleanup of temp folders and worktrees.

### Modified Capabilities

None. There are no main specs yet; the current behaviour is described by `plugins/base/skills/review-mr/SKILL.md`, which these specs replace in the parts they cover.

## Impact

- `plugins/base/skills/review-mr/SKILL.md`: steps 0, 2a, 4, 5 and the end of 7 change; new steps for checks and run-it. Frontmatter gains `--fast` and `--keep-worktrees` in `argument-hint` and `usage-report` in `dependencies`.
- `plugins/base/skills/review-mr/references/agent-brief.md`: new lenses, context rules, temp-folder rules, leftovers line in the report.
- New scripts with tests under `plugins/base/skills/review-mr/`: `scripts/find_conventions.py`, `scripts/run_checks.py`, `scripts/run_cost.py`.
- Reads `add-usage-collection` (price table, per-request pricing, tier rule). This change should land after it, or fall back to token counts without USD.
- Related to `add-cleanup` (a `/base:cleanup` safety-net skill): this change only makes the review run clean up its own temp folders and worktrees and does not call that skill.
- Cost: a typical review runs more, smaller agents on a cheaper model. The benchmark rerun (last task group) decides whether the numbers hold.
- Release: `feat(base)`, minor bump.

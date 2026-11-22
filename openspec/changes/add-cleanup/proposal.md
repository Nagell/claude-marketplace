# Proposal

## Why

Tests, tries and new worktrees leave things behind: merged branches, worktree folders for finished work and scratch directories in `/tmp`. They add up. Today `git worktree list` in this repo shows four worktrees whose work is merged, `git branch -vv` shows six merged local branches, and 207 of 217 dead-session scratchpads for this project are empty or stale.

The main rule is already in place: the agent that creates scratch work deletes it (see `plugins/base/CLAUDE.md` and the review-mr agent brief). Searching `/tmp` for leftovers is expensive in tokens, so cleanup must not rely on an agent exploring. A safety net is still needed for what is already there and for agents that stop early.

## What Changes

- Add a `cleanup` skill to the `base` plugin, invoked as `/base:cleanup`.
- The work is done by one deterministic Python 3 script (stdlib only). It scans known locations only, prints a compact candidate list and removes only what the user approved. The skill shows the list and asks once.
- Candidates: merged local branches, merged remote branches, worktrees of merged work that are clean and pushed, orphan worktree folders and scratchpads of sessions that are no longer running.
- Remote branch deletion is a push. It goes through the existing push token gate in `safety-guards.sh`, once per push, after the user approves.
- Dry run is the default. Every removal is logged.
- Document the skill in the `base` README and the root README skill tables.

## Capabilities

### New Capabilities

- `cleanup-candidates`: which leftovers the skill finds, how "merged" and "session not running" are decided, and where it looks.
- `cleanup-removal`: how the user approves, what is never deleted, how risky items are handled, how remote deletes pass the push gate, and what is logged.

### Modified Capabilities

None. The repo has no main specs yet.

## Impact

- New files under `plugins/base/skills/cleanup/`: `SKILL.md`, `scripts/cleanup.py`, `tests/test_cleanup.py`.
- Edited docs: `plugins/base/README.md` and `README.md` (skill tables).
- Conventional commit `feat(base): add cleanup skill` gives a minor bump through Release Please.
- Runtime needs: `git`, `python3`. Optional: `gh` or `glab` for squash merges. No change to hooks.
- Out of scope: scanning arbitrary `/tmp` or `$HOME`, cleaning other tools' caches, deleting branches of other repos, and changing the existing cleanup rule.

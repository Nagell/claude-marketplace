# Proposal

## Why

Tests, tries and new worktrees leave things behind: merged branches, worktree folders for finished work and scratch folders in `/tmp`. They add up. On 2026-11-22, after `git fetch --prune`, this repo has two worktrees whose branches are merged, two more merged local branches, and 210 stale scratch folders of sessions that are no longer running (189 empty, 21 still holding files).

The main rule is already in place: the agent that creates scratch work deletes it (see `plugins/base/CLAUDE.md` and the review-mr agent brief). Searching `/tmp` for leftovers is expensive in tokens, so cleanup must not rely on an agent exploring. A safety net is still needed for what is already there and for agents that stop early. Today agents create their folders with plain `mktemp -d`, which puts them in `/tmp/tmp.*`, where no cheap scan can tell whose they are.

## What Changes

- Add a `cleanup` skill to the `base` plugin, invoked as `/base:cleanup`.
- The work is done by one deterministic Python 3 script (stdlib only). It scans known locations only, prints a compact candidate list and removes only what the user approved. The skill shows the list and asks once.
- Candidates: merged local branches, merged remote branches, worktrees of merged work that are clean and pushed, orphan worktree folders and session scratch folders of sessions that are no longer running.
- Remote branch deletion is a push. It goes through the existing push token gate in `safety-guards.sh`, once per push, after the user approves.
- Dry run is the default. Every removal is logged.
- Change where the cleanup rule puts throwaway work: one folder made with `mktemp -d -p <session scratchpad>` instead of plain `mktemp -d`, so the skill can find an agent's forgotten folder in the current session.
- Document the skill in the `base` README skill table, the base row of the root README plugin table and `plugins/base/CLAUDE.md`.

## Capabilities

### New Capabilities

- `cleanup-candidates`: which leftovers the skill finds, how "merged" and "session not running" are decided, and where it looks.
- `cleanup-removal`: how the user approves, what is never deleted, how risky items are handled, how remote deletes pass the push gate, and what is logged.

### Modified Capabilities

None. The repo has no main specs yet.

## Impact

- New files under `plugins/base/skills/cleanup/`: `SKILL.md`, `scripts/cleanup.py`, `tests/test_cleanup.py`.
- Edited docs: `plugins/base/README.md` (skill table) and `README.md` (base row description in the plugin table).
- Edited rules: `plugins/base/CLAUDE.md` (Scratch Work & Cleanup: the `mktemp -d -p <session scratchpad>` rule and one line pointing to `/base:cleanup`) and `plugins/base/skills/review-mr/references/agent-brief.md` (same `mktemp` rule). The user keeps `~/.claude/CLAUDE.md` identical to the template and syncs it.
- Conventional commit `feat(base): add cleanup skill` gives a minor bump through Release Please.
- Runtime needs: `git`, `python3`. Optional: `gh` or `glab` for squash merges. No change to hooks.
- Out of scope: scanning arbitrary `/tmp` or `$HOME`, cleaning other tools' caches and deleting branches of other repos. The rule that each agent deletes its own scratch work stays; only the folder location changes.

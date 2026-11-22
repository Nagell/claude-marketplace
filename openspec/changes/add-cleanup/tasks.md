# Tasks

## 1. Script skeleton and merge detection

- [ ] 1.1 Create `plugins/base/skills/cleanup/scripts/cleanup.py` with `scan` and `remove` commands, repo and primary-checkout discovery, default branch lookup and `git fetch --prune origin`. Verify `python3 cleanup.py scan --help` and `remove --help` run on Python 3.9+.
- [ ] 1.2 Implement the merged check (ancestor, PR/MR head match through `gh` or `glab`, `git cherry`). Add `tests/test_cleanup.py` with throwaway repos built in a `tempfile` folder: regular, squash (stubbed `gh` output), rebase, reused branch and stale local `main`. Verify `python3 -m unittest` passes.
- [ ] 1.3 Implement local and remote branch candidates with the protected list. Verify tests for current branch, primary checkout branch, `release-please--*` and open-PR branch.

## 2. Worktrees and orphan folders

- [ ] 2.1 Parse `git worktree list --porcelain` and classify worktrees as safe, risky, dangling or in use (clean status with untracked files, unpushed commits, lock, session `cwd`). Verify tests for each class.
- [ ] 2.2 Detect orphan folders under `<repo>.worktrees/` and `<repo>-*` by the `.git` file pointer, and report other folders as unknown. Verify a sibling with a `.git` directory is never a candidate.

## 3. Session scratchpads

- [ ] 3.1 Read `~/.claude/sessions/*.json`, decide liveness (pid, `/proc/<pid>/stat` start time on Linux, fail safe elsewhere). Verify tests with a live pid, a dead pid and a reused pid.
- [ ] 3.2 Scan `/tmp/claude-<uid>/` for stale scratchpads (age by newest `lstat` mtime, project scope, `--all-projects`, `--days`), group empty ones and handle symlinks. Verify a test with a symlink to a folder outside the root leaves the target intact.
- [ ] 3.3 Add `--own <scratchpad>` for `mktemp -d` shaped folders. Verify `tmp.Ab12Cd34Ef` is listed and `notes.md` and `explore` are not.

## 4. Output, removal and log

- [ ] 4.1 Print the grouped table with ids, summary line and the 40-line cap, and write `last-scan.json`. Verify a run on this repo prints the example candidates from design.md and fits in about 40 lines.
- [ ] 4.2 Implement `remove --ids ... [--apply] [--allow-risky ...]` with dry run default, re-verification before each deletion, `git worktree remove` without force, branch tip logging and the JSON-lines log. Verify tests: dry run deletes nothing, a worktree made dirty after the scan is skipped, a refused `git worktree remove` is reported and the log holds the tip commit id.
- [ ] 4.3 Verify the script never calls `git push` (grep in a test) and that remote candidates produce a printed `git push origin --delete` command only.

## 5. Skill and docs

- [ ] 5.1 Write `plugins/base/skills/cleanup/SKILL.md` (frontmatter with `disable-model-invocation: true`, no `dependencies:`; steps for scan, one AskUserQuestion, per-item risky questions, remove, remote push with the separate token call). Verify the flow by a dry run in this repo and compare with the example list.
- [ ] 5.2 Add the skill to the skill tables in `plugins/base/README.md` and `README.md`, and one line in `plugins/base/CLAUDE.md` pointing to `/base:cleanup` as the safety net. Verify with `grep -n "cleanup" README.md plugins/base/README.md plugins/base/CLAUDE.md`.

## 6. Integration checks

- [ ] 6.1 On a throwaway clone with a merged branch, a clean merged worktree and a stale scratchpad, run the skill end to end with an approved push to a bare local remote. Verify the push hook asks for the token, the branch is gone on the remote and the log has one line per removal.
- [ ] 6.2 Run `python3 -m unittest` on Linux and run the scan on a Mac. Verify the Mac scratch root and that a live session keeps its scratchpad.

## Workflow follow-up

- Commit with `feat(base): add cleanup skill` after review. Do not push without confirmation.
- Archive the change once the skill is merged.

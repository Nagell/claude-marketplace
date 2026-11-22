# Tasks

Run tests from `plugins/base/skills/cleanup/` with `python3 -m unittest discover -s tests`.

## 1. Script skeleton and merge detection

- [ ] 1.1 Create `plugins/base/skills/cleanup/scripts/cleanup.py` with `scan` and `remove` commands, repo and primary-checkout discovery, default branch lookup and `git fetch --prune origin`. The scratch root and sessions folder are function arguments so tests can use fixtures. Verify `python3 cleanup.py scan --help` and `remove --help` run on Python 3.9+.
- [ ] 1.2 Implement the merged check (ancestor, PR/MR head match through `gh pr list ... --json` or `glab mr list --merged -F json`, `git cherry`). Add `tests/test_cleanup.py` with throwaway repos built in a `tempfile` folder: regular, squash (stubbed `gh` output), rebase, reused branch and stale local `main`. Add a case with no `gh` and no `glab` that checks the output names the skipped check. Verify the test command passes.
- [ ] 1.3 Implement local and remote branch candidates with the protected list. Verify tests for current branch, primary checkout branch, protected patterns, a merged `release-please--*` branch (listed) and open-PR branch.

## 2. Worktrees and orphan folders

- [ ] 2.1 Parse `git worktree list --porcelain` and classify worktrees as safe, risky, dangling or in use (clean status with untracked files, unpushed commits, lock, session `cwd`, an ignored file missing in or different from the primary checkout). Verify tests for each class, including an identical ignored `.env` (safe), a different one (risky), a worktree holding only ignored build output such as `dist/` and `node_modules/` (safe) and a detached worktree whose commit is in `origin/main` (safe).
- [ ] 2.2 Detect orphan folders under `<repo>.worktrees/` and `<repo>-*` by the `.git` file pointer, and report other folders as unknown. Verify a sibling with a `.git` directory is never a candidate.

## 3. Session scratch folders

- [ ] 3.1 Read `~/.claude/sessions/*.json`, decide liveness (pid, `/proc/<pid>/stat` start time on Linux compared as a string, fail safe elsewhere). Verify tests with a live pid, a dead pid, a reused pid, a file without `procStart` whose pid exists (running), a `procStart` stored as a string, and a non-JSON `*.key` file and a broken JSON file (both skipped).
- [ ] 3.2 Scan the scratch root for stale session folders: only folders whose name starts with `-` are project folders; age by newest `lstat` mtime of anything inside; project scope by exact encoded path of the primary checkout or a registered worktree, or `<encoded>-<rest>` where `<rest>` encodes an existing folder in the repo or a worktree; `--all-projects`; `--days`. A folder with no regular file except `started` is empty and safe (grouped). Any other file makes it risky, listed with size and newest files. Verify tests: a symlink to a folder outside the root leaves the target intact; a sibling-repo folder such as `-...-claude-marketplace-template` is out of scope; a non-project folder such as `node-compile-cache` is never read, also with `--all-projects`; a folder holding only `started` and empty subfolders is safe; a folder with a file in `tasks/` is risky; a folder with a recent file is not listed; a stale folder with no session file is listed; unrelated folders in a fixture `/tmp` stand-in outside the scratch root are not read.
- [ ] 3.3 Add `--own <scratchpad>` for `mktemp -d` shaped folders. Verify `tmp.Ab12Cd34Ef` is listed, `notes.md` and `explore` are not, and the current working directory is not listed even when its name has the `mktemp` shape.

## 4. Output, removal and log

- [ ] 4.1 Print the grouped table with ids, summary line and the 40-line cap, and write `last-scan.json`. Verify tests: no candidates prints one line and exits 0; more than 40 items prints the oldest or largest first, a summary line counts the rest and the scan file holds all of them. Then run the scan on this repo and check its items against live `git worktree list --porcelain`, `git branch -vv`, `git ls-remote --heads origin` and `gh pr list --state merged` output, not against the example in design.md.
- [ ] 4.2 Implement `remove --ids ... [--apply] [--allow-risky ...]` with dry run default, re-verification before each deletion, `git worktree remove` without force, removal of the whole `<session>/` folder with `shutil.rmtree`, branch tip logging and the JSON-lines log. Verify tests: dry run deletes nothing; a worktree made dirty after the scan is skipped; a refused `git worktree remove` is reported; a worktree and its branch are removed worktree first; a branch checked out in another worktree is not deleted; a session path that resolves outside the scratch root is refused; a removed session folder is gone with its `tasks/` and `started`; the log holds the tip commit id.
- [ ] 4.3 Verify the script never calls `git push` (grep in a test) and that remote candidates produce a printed `git push origin --delete` command only.

## 5. Skill, rule and docs

- [ ] 5.1 Write `plugins/base/skills/cleanup/SKILL.md` (frontmatter with `disable-model-invocation: true`, no `dependencies:`; steps for scan, one AskUserQuestion, per-item risky questions, remove, remote push with the separate token call). Verify the flow by a dry run in this repo and check the listed items against the same live git and `gh` output as in 4.1.
- [ ] 5.2 Add the skill to the skill table in `plugins/base/README.md`, add "cleanup" to the base row description in the root `README.md` plugin table, and add one line in `plugins/base/CLAUDE.md` pointing to `/base:cleanup` as the safety net. Verify with `grep -n "cleanup" README.md plugins/base/README.md plugins/base/CLAUDE.md`.
- [ ] 5.3 Change the scratch rule in `plugins/base/CLAUDE.md` (Scratch Work & Cleanup) and in `plugins/base/skills/review-mr/references/agent-brief.md`: all throwaway work (stubs, installs, test repos, throwaway clones, anything bigger than a single file) goes in one folder made with `mktemp -d -p <session scratchpad>`, with plain `mktemp -d` only when no scratchpad is named. Say that real worktrees stay in `<repo>.worktrees/`. Remind the user to sync `~/.claude/CLAUDE.md`, which must stay identical to `plugins/base/CLAUDE.md`. Verify with `grep -n "mktemp" plugins/base/CLAUDE.md plugins/base/skills/review-mr/references/agent-brief.md`.

## 6. Integration checks

- [ ] 6.1 On a throwaway clone with a merged branch, a clean merged worktree and a stale session folder, run the skill end to end with an approved push to a bare local remote. Build all fixtures under `mktemp -d -p <session scratchpad>`, create `.env` fixtures from Python, and delete fixtures with Python, not with `rm -rf` plus a `/home/<user>/` path, which the hook blocks. Run the push step inside a Claude Code session with the base plugin enabled. Verify the push hook asks for the token, the branch is gone on the remote and the log has one line per removal.
- [ ] 6.2 Run `python3 -m unittest discover -s tests` on Linux and run the scan on a Mac. Verify the Mac scratch root, that BSD `mktemp -d -p` works, and that a live session keeps its scratch folder.

## Workflow follow-up

- Commit with `feat(base): add cleanup skill` after review. Do not push without confirmation.
- Archive the change once the skill is merged.

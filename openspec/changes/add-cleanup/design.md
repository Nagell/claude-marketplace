# Design

## Context

See proposal.md for the motivation. Facts that shape the approach, checked on this machine:

- Precedent for a skill with a Python script and tests: `plugins/base/skills/review-mr/` (`scripts/*.py`, `tests/test_*.py`, `disable-model-invocation: true`). review-mr tests use pytest, which is not installed here. The precedent for stdlib `unittest` is `plugins/base/skills/setup-zsh/tests/`. Tests run with `python3 -m unittest discover -s tests` from the skill folder; plain `python3 -m unittest` finds nothing because `tests/` has no `__init__.py`.
- `plugins/base/hooks/safety-guards.sh` gates `git push` by reading the Bash command text. A push inside a script is invisible to it. The hook wants `.claude-push-token` in the repo root, created by the agent in its own Bash call after the user said yes, and removes the token in PreToolUse, before the push runs, whatever its outcome.
- The same hook blocks any shell command that holds `rm -rf` together with a `/home/<user>/` path, and blocks writing a `.env` with echo, printf or cat. The script deletes with `shutil.rmtree` and is not affected. Shell setup in integration tests is.
- `~/.claude/sessions/<pid>.json` holds `pid` (int), `sessionId`, `cwd` and usually `procStart` (a string, for example `"1636406"`). 126 JSON files exist here, only 5 are live. Three more name a pid that was reused by another process: `procStart` matches field 22 of `/proc/<pid>/stat` only for a live session. One old file has no `procStart`. The folder also holds 103 non-JSON `*.key` files.
- Scratch folders live at `/tmp/claude-<uid>/<project>/<session>/`, with `scratchpad/` inside. A session folder can also hold `tasks/` (task output, up to 133 KB here), `images/` and a `started` marker. `<project>` is the working directory with `/`, `_` and `.` turned into `-`, so it always starts with `-`. Sessions started in a subfolder get their own project folder. The encoding is lossy: the sibling repo `claude-marketplace-template` would encode to a name that starts with this repo's encoded path.
- The scratch root also holds folders that are not projects: `bash-edit-diff`, `bundled-skills`, `hh`, `node-compile-cache`, `nojq`.
- `TMPDIR` is empty here, so plain `mktemp -d` creates `/tmp/tmp.XXXXXXXXXX`. Five such folders exist in `/tmp`; none exist in any scratchpad.
- Local `main` is 88 commits behind `origin/main` here. Upstream tracking can point at the wrong branch. Upstream tracking and local `main` are not reliable references.

## Goals / Non-Goals

**Goals:**
- Near zero token cost: the script does all scanning and deleting, the model only relays one table and one question.
- Never lose work: every deletion is provably merged and clean, or explicitly approved per item.
- Same behavior on Linux, WSL and macOS.

**Non-Goals:**
- No search of `/tmp` or `$HOME`, no cleanup of other tools' caches, no other repositories (unless `--all-projects` for scratch folders).
- No background daemon or hook that runs cleanup on its own.
- No change to the rule that agents delete their own scratch work. Only the place where they create it changes (decision 5).

## Decisions

### 1. One Python script with `scan` and `remove` commands

`plugins/base/skills/cleanup/scripts/cleanup.py`, stdlib only, calls `git` (and `gh` or `glab` when present) through `subprocess` with argument lists.

- `scan` fetches `origin` with prune, collects candidates, writes `last-scan.json` next to the log and prints the table. It deletes nothing. Its only writes are the fetch (which also prunes stale remote-tracking refs) and the scan file.
- `remove --ids b1,w2,s3 [--apply] [--allow-risky w4]` loads the scan file, re-verifies each item, then deletes. Without `--apply` it prints the plan (dry run).
- Ids are short and stable per scan: `b` local branch, `r` remote branch, `w` worktree, `o` orphan folder, `s` session scratch folder, `m` own session leftover.
- The scratch root and the sessions folder are function arguments, so unit tests point them at fixtures. The log folder follows `XDG_STATE_HOME`.

Alternative rejected: POSIX sh. Merge checks, JSON from `gh` and session files, and macOS versus Linux `stat` and `date` differences make it longer and more fragile than Python. Alternative rejected: the model runs git commands itself. It costs tokens on every run and each run could differ.

### 2. Merged means contained in `origin/<default>`, with two fallbacks

Order of checks per branch tip:
1. `git merge-base --is-ancestor <tip> origin/<default>` after `git fetch --prune origin`. Default branch comes from `refs/remotes/origin/HEAD`, else `main`, else `master`.
2. Merged PR or MR with the same head commit: `gh pr list --state merged --limit 200 --json number,headRefName,headRefOid` or `glab mr list --merged -F json` (fields `source_branch`, `sha`). This is the only reliable test for squash merges. Platform comes from the `origin` host. The `glab` fields are not verified here, because `origin` is on GitHub.
3. `git cherry origin/<default> <tip>` shows no `+` lines. This catches rebase merges when no CLI is installed.

A branch whose tip differs from the PR head is "reused" and shown as risky. Squash merges with no CLI are reported as undetectable, not guessed. In this repo all merged branches are plain ancestors of `origin/main`, so check 1 covers today's state; checks 2 and 3 are for future squash and rebase merges and get unit tests with synthetic repos.

Alternative rejected: `git branch --merged main`. It uses the stale local `main` and misses squash and rebase merges. Alternative rejected: trusting the branch's upstream tracking, which can point at the wrong branch.

### 3. Worktrees: merged, clean, pushed, not in use

From `git worktree list --porcelain`. Safe means: branch merged (or detached commit contained in `origin/<default>`), `git status --porcelain --untracked-files=all` empty, no commits outside the merged head, not locked, not the primary checkout, not the current worktree, not the `cwd` of a running session. An ignored file makes the worktree risky only when the primary checkout has no identical file at the same path; files under `node_modules`, `dist`, `.nuxt`, `.output`, `build`, `coverage` and `__pycache__` never count. Removal uses `git worktree remove` without `--force`, so git is a second safety check. The one exception is a risky worktree with changed files that the user approved on its own: the question lists the changed files and the commits that would be lost, the script checks that nothing changed since the scan, then runs `git worktree remove --force`. The safe group and items without their own yes are never forced. Commits after a merged PR are named by subject (first 5, then "and N more"), not only counted. A worktree whose folder is gone is "dangling" and is pruned with `git worktree prune`.

Orphan folders (`<repo>.worktrees/*`, `<repo>-*`) are reported only when `.git` is a file pointing at a missing `.git/worktrees/<name>`. A sibling with a `.git` directory is another repository (for example `claude-marketplace-template` next to this repo) and is never touched. Orphans are always risky: with the admin data gone, uncommitted work cannot be checked.

### 4. Session scratch folders: session not running and older than N days

The unit is the whole session folder `/tmp/claude-<uid>/<project>/<session>/`. Removal deletes all of it, including `scratchpad/`, `tasks/`, `images/` and `started`.

Not running = no file in `~/.claude/sessions/` names the session with a live process whose `procStart` matches. On Linux the match uses `/proc/<pid>/stat` field 22, compared as a string. A session file without `procStart` counts as running when its pid exists (fail safe). Non-JSON files and files that do not parse are skipped. On macOS there is no `/proc`, so an existing pid counts as running (fail safe, keeps the folder). Age = newest mtime of anything inside the folder, default 7 days (`--days`). The walk uses `lstat` and never follows symlinks; removal uses `shutil.rmtree`, which removes links without following them. Paths must resolve under `/tmp/claude-<uid>/`. A scratch root derived from `--own` is used only when it resolves under `/tmp/claude-<uid>/`; otherwise the scan falls back to `/tmp/claude-<uid>/`.

Empty means no regular file anywhere inside the session folder except the `started` marker. Empty folders (subfolders included) are safe and grouped into one entry with a count, because most are empty (189 here) and one line each would cost tokens. A stale folder that holds any other file, even a zero-byte one, is risky: task output, an image or a scratch file. It is listed with size and newest files and needs its own yes.

Scope. Only folders in the scratch root whose name starts with `-` are project folders; the others are never read, also with `--all-projects`. By default a project folder belongs to this repository when its name is exactly the encoded path of the primary checkout or of a registered worktree, or `<encoded>-<rest>` where `<rest>` is the encoding of a folder that exists inside the repository or one of its worktrees. A plain prefix match is not enough, because of the lossy encoding. `--all-projects` scans every project folder.

Alternative rejected: age of the `<session>` folder itself. Its mtime does not change when files deep inside change. Alternative rejected: judging emptiness by `scratchpad/` only. It would delete `tasks/` output as "empty".

### 5. Own session leftovers and the mktemp rule

Today the rule in `plugins/base/CLAUDE.md` and in the review-mr agent brief says to use plain `mktemp -d`, so agents' folders land in `/tmp/tmp.*`. The scan must not search `/tmp`, so it cannot find them. The rule changes: all throwaway work (stubs, installs, test repos, throwaway clones, anything bigger than a single file) goes in one folder made with `mktemp -d -p <session scratchpad>`. When no scratchpad is named, agents fall back to plain `mktemp -d`, and the own-session group does not cover that case. Real worktrees stay in `<repo>.worktrees/` and are covered by the worktree group (decision 3), not by this rule. The user keeps `~/.claude/CLAUDE.md` identical to `plugins/base/CLAUDE.md` and syncs it after the change.

`scan --own <scratchpad>` adds group `m`, shown first. Only directories in that scratchpad shaped like `mktemp -d` output are listed (`tmp.XXXXXXXXXX` or a name ending in `.`/`-` plus at least six random characters). Plain files and other folders in the scratchpad are never listed, because a report or a build folder may be wanted. The current working directory is never listed. No age limit, because the user is still in the session and approves explicitly.

### 6. Approval flow in the skill

1. Run `cleanup.py scan --own <scratchpad>`. Show the table as is.
2. One AskUserQuestion: delete all safe items (recommended), delete all except some (user types ids through the free-text answer), cancel. AskUserQuestion cannot list 40 options, so the table carries the ids and the dialog carries only the choice. Remote branches are a separate question in the same dialog, worded as a push.
3. Risky items: one AskUserQuestion per item (up to four per call), naming the files or commits that would be lost. A "no" keeps the item.
4. Run `cleanup.py remove --ids ... --apply`. Print counts and the log path.
5. Remote branches, if approved: `cleanup.py log-remote --ids r1,r2` logs each branch with its tip and prints the push command (decision 7). Then `touch <primary root>/.claude-push-token` in its own Bash call, then `git -C <primary root> push origin --delete a b c` in the next call. One push, one token. The primary root is used so the hook resolves the same repo root from `git -C`.

The script never runs `git push`. The hook reads the command text, so a push hidden in a script would skip the gate the user relies on, and a gate that needs the script to ask for a token cannot work. Alternatives rejected: `gh api -X DELETE .../git/refs/heads/<b>` (deletes remote refs without the hook seeing a `git push`, which defeats the gate); asking once for a permanent token (the hook and the user's rule require a token per push).

### 7. Log and recovery

JSON lines in `${XDG_STATE_HOME:-~/.local/state}/claude-cleanup/cleanup.log`. Branch entries keep the tip commit id, so `git branch <name> <sha>` restores a branch. Remote branches are logged by `log-remote` before the push, one entry per branch with its tip, so `git push origin <sha>:refs/heads/<name>` restores one. Worktree and session folder deletions cannot be undone, which is why clean and not-running checks are strict.

### 8. Skill shape

`plugins/base/skills/cleanup/SKILL.md` with `disable-model-invocation: true` (destructive, user invokes `/base:cleanup`). No `dependencies:` entry: it relies on no other skill, only on the `safety-guards.sh` hook, which the skill text names. The skill tells the model never to run `ls`, `find` or `du` on `/tmp` and to use only the script output.

## Real current state, example

Checked on 2026-11-22 after `git fetch --prune origin`, with `git worktree list`, `git branch -vv`, `git ls-remote --heads origin`, `gh pr list --state merged` and `git status` in each worktree. Read only otherwise. This is a snapshot; tasks verify against live output, not against this table.

| id | kind | item | why | class |
|----|------|------|-----|-------|
| b1 | local branch | `docs/plugin-readme-format` | PR #229 merged, upstream gone | safe |
| b2 | local branch | `feat/base-drop-playwright-mcp` | PR #233 merged, upstream gone | safe |
| w1 | worktree + branch | `claude-marketplace.worktrees/cleanup-rule`, `chore/cleanup-rule` | PR #244 merged at the same tip `ef1258e`, clean, no ignored files | safe |
| w2 | worktree + branch | `claude-marketplace.worktrees/review-mr-plan`, `docs/review-mr-plan-refuters` | PR #246 merged, 4 changed or untracked files | risky |
| s1 | session folders | 189 stale sessions with no files except `started` | not running, older than 7 days | safe, grouped |
| s2..s22 | session folder | 21 stale sessions holding files, for example `d41c14aa` (292 days, 3.5 KB), `13ad92cd` (218 days, 133 KB), `c31e2708` (66 days, 65 KB), `b1238b4d` (14 days, 21 MB) | not running, older than 7 days, not empty | risky, asked one by one |

No remote candidates today: `origin` holds only `main`. An earlier check the same day saw merged remote branches, among them six `release-please--branches--main--components--*` branches (base, browser, dev-extras, extras, openspec-extras, review). They were gone at this fetch. When such branches exist and are merged, they are listed as `r` items and deleted in one push.

Never listed:
- `chore/openspec-init` (primary checkout branch; PR #243 is merged, but the branch is checked out).
- `main`, the primary checkout, and the scratch folders of the 5 live sessions (one of them in this project).
- `w2` when the scan runs from inside that worktree (current worktree).

Reported as unknown, never deleted: `claude-marketplace-template` (sibling with its own `.git` directory). No own-session leftovers (`m`) exist today, because agents still use plain `mktemp -d`.

## Risks / Trade-offs

- [Squash merge with no `gh` or `glab`] is undetectable → reported as "needs gh or glab", never guessed.
- [`gh` rate limits or no auth] → fall back to checks 1 and 3 and print which check was skipped.
- [Session file missing for a live session] → age limit (7 days) bounds the risk; an active session touches its folder.
- [Ignored files lost with a worktree, for example a local `.env`] → risky when the primary checkout has no identical copy, so it needs its own yes.
- [Forced removal of an approved dirty worktree deletes its changes for good] → only after its own yes, with the changed files and lost commits named in the question, and only when the worktree is unchanged since the scan.
- [Large state cut at 40 rows] → the oldest and largest items fill the table; younger items are counted in the summary line and stay in the scan file.
- [macOS liveness is weaker] → fail safe: keep the folder when a pid exists.
- [Many risky session folders] → 21 here means about six dialogs of four questions. Accepted: task output and images may be wanted.
- [Remote delete partially fails] → report git's message, no automatic retry, no second token without asking.
- [Plan goes stale between scan and remove] → each item is re-verified immediately before deleting.

## Open Questions

Decided by the user in the grill (2026-11-22):

1. Scratch scope defaults to this repository's project folders, with `--all-projects` as opt-in.
2. Default age is 7 days (`--days`). Only empty stale session folders are safe; one that still holds files is risky and asked about on its own.
3. Merged `release-please--*` branches are deleted like other merged branches.
4. An ignored file makes a worktree risky only when the primary checkout has no identical file at the same path. `git worktree add` copies no ignored files; Claude Code copies only those listed in `.worktreeinclude` (not verified against its docs).
5. The own-session group matches only `mktemp -d` shaped names.
6. The remote-branch question in the single dialog, worded as a push, counts as the yes for that one push.
7. Only `origin` is handled.

Decided by the user after the plan check (2026-11-22):

8. Agents create throwaway work with `mktemp -d -p <session scratchpad>`; the rule in `plugins/base/CLAUDE.md` and the agent brief changes.
9. Removal deletes the whole `<session>/` folder. Empty means no regular file except `started`.

Still open: on macOS, whether the scratch root is `/tmp/claude-<uid>` or under `$TMPDIR`, and whether BSD `mktemp` accepts `-d -p`. Verify on a Mac in the macOS support task.

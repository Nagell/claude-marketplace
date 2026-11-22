# Design

## Context

See proposal.md for the motivation. Facts that shape the approach, checked on this machine:

- Precedent for a skill with a Python script and tests: `plugins/base/skills/review-mr/` (`scripts/*.py`, `tests/test_*.py`, `disable-model-invocation: true`).
- `plugins/base/hooks/safety-guards.sh` gates `git push` by reading the Bash command text. A push inside a script is invisible to it. The hook wants `.claude-push-token` in the repo root, created by the agent in its own Bash call after the user said yes, and removes the token after one push.
- `~/.claude/sessions/<pid>.json` holds `pid`, `sessionId`, `procStart`, `cwd`. 126 files exist here, only 5 are live. Three more name a pid that was reused by another process: `procStart` matches field 22 of `/proc/<pid>/stat` only for a live session.
- Scratchpads live at `/tmp/claude-<uid>/<project>/<session>/scratchpad`. `<project>` is the working directory with `/`, `_` and `.` turned into `-`. Sessions started in a subfolder or a worktree get their own project folder.
- Local `main` is 76 commits behind `origin/main` here, and `fix/push-gate-bypass` tracks the wrong upstream (`origin/fix/review-237-238`). Upstream tracking and local `main` are not reliable references.

## Goals / Non-Goals

**Goals:**
- Near zero token cost: the script does all scanning and deleting, the model only relays one table and one question.
- Never lose work: every deletion is provably merged and clean, or explicitly approved per item.
- Same behavior on Linux, WSL and macOS.

**Non-Goals:**
- No search of `/tmp` or `$HOME`, no cleanup of other tools' caches, no other repositories (unless `--all-projects` for scratchpads).
- No background daemon or hook that runs cleanup on its own.
- No change to the existing rule that agents delete their own scratch work.

## Decisions

### 1. One Python script with `scan` and `remove` commands

`plugins/base/skills/cleanup/scripts/cleanup.py`, stdlib only, calls `git` (and `gh` or `glab` when present) through `subprocess` with argument lists.

- `scan` fetches `origin`, collects candidates, writes `last-scan.json` next to the log and prints the table. Read only.
- `remove --ids b1,w2,s3 [--apply] [--allow-risky w4]` loads the scan file, re-verifies each item, then deletes. Without `--apply` it prints the plan (dry run).
- Ids are short and stable per scan: `b` local branch, `r` remote branch, `w` worktree, `o` orphan folder, `s` scratchpad, `m` own session leftover.

Alternative rejected: POSIX sh. Merge checks, JSON from `gh` and session files, and macOS versus Linux `stat` and `date` differences make it longer and more fragile than Python. Alternative rejected: the model runs git commands itself. It costs tokens on every run and each run could differ.

### 2. Merged means contained in `origin/<default>`, with two fallbacks

Order of checks per branch tip:
1. `git merge-base --is-ancestor <tip> origin/<default>` after `git fetch --prune origin`. Default branch comes from `refs/remotes/origin/HEAD`, else `main`, else `master`.
2. Merged PR or MR with the same head commit: `gh pr list --state merged --limit 200 --json number,headRefName,headRefOid` or `glab mr list --merged` (fields `source_branch`, `sha`). This is the only reliable test for squash merges. Platform comes from the `origin` host.
3. `git cherry origin/<default> <tip>` shows no `+` lines. This catches rebase merges when no CLI is installed.

A branch whose tip differs from the PR head is "reused" and shown as risky. Squash merges with no CLI are reported as undetectable, not guessed. In this repo all merged branches are plain ancestors of `origin/main`, so check 1 covers today's state; checks 2 and 3 are for future squash and rebase merges and get unit tests with synthetic repos.

Alternative rejected: `git branch --merged main`. It uses the stale local `main` and misses squash and rebase merges. Alternative rejected: trusting the branch's upstream tracking, which is wrong for `fix/push-gate-bypass`.

### 3. Worktrees: merged, clean, pushed, not in use

From `git worktree list --porcelain`. Safe means: branch merged (or detached commit contained in `origin/<default>`), `git status --porcelain --untracked-files=all` empty, no commits outside the merged head, not locked, not the primary checkout, not the current worktree, not the `cwd` of a running session. Ignored files do not block (build output is normal). Removal uses `git worktree remove` without `--force`, so git is a second safety check. A worktree whose folder is gone is "dangling" and is pruned with `git worktree prune`.

Orphan folders (`<repo>.worktrees/*`, `<repo>-*`) are reported only when `.git` is a file pointing at a missing `.git/worktrees/<name>`. A sibling with a `.git` directory is another repository (for example `afdverbieten-frontend` next to `afdverbieten-backend`) and is never touched. Orphans are always risky: with the admin data gone, uncommitted work cannot be checked.

### 4. Scratchpads: session not running and older than N days

Not running = no file in `~/.claude/sessions/` names the session with a live process whose `procStart` matches. On Linux the match uses `/proc/<pid>/stat` field 22. On macOS there is no `/proc`, so an existing pid counts as running (fail safe, keeps the folder). Age = newest mtime in the folder, default 7 days (`--days`). The walk uses `lstat` and never follows symlinks; removal uses `shutil.rmtree`, which removes links without following them. Paths must resolve under `/tmp/claude-<uid>/`.

By default only project folders that start with this repository's encoded path are scanned (covers its worktrees and subfolders). `--all-projects` scans every project folder.

Empty stale scratchpads are grouped into one entry with a count, because most are empty (207 here) and one line each would cost tokens.

Alternative rejected: age of the `<session>` folder itself. Its mtime does not change when files deep inside change.

### 5. Own session leftovers

`scan --own <scratchpad>` adds group `m`, shown first. Only directories shaped like `mktemp -d` output are listed (`tmp.XXXXXXXXXX` or a name ending in `.`/`-` plus at least six random characters). Plain files and other folders in the scratchpad are never listed, because a report or a build folder may be wanted. No age limit, because the user is still in the session and approves explicitly.

### 6. Approval flow in the skill

1. Run `cleanup.py scan --own <scratchpad>`. Show the table as is.
2. One AskUserQuestion: delete all safe items (recommended), delete all except some (user types ids through the free-text answer), cancel. AskUserQuestion cannot list 40 options, so the table carries the ids and the dialog carries only the choice. Remote branches are a separate question in the same dialog, worded as a push.
3. Risky items: one AskUserQuestion per item (up to four per call), naming the files or commits that would be lost. A "no" keeps the item.
4. Run `cleanup.py remove --ids ... --apply`. Print counts and the log path.
5. Remote branches, if approved: `touch <primary root>/.claude-push-token` in its own Bash call, then `git -C <primary root> push origin --delete a b c` in the next call. One push, one token. The primary root is used so the hook resolves the same repo root from `git -C`.

The script never runs `git push`. The hook reads the command text, so a push hidden in a script would skip the gate the user relies on, and a gate that needs the script to ask for a token cannot work. Alternatives rejected: `gh api -X DELETE .../git/refs/heads/<b>` (deletes remote refs without the hook seeing a `git push`, which defeats the gate); asking once for a permanent token (the hook and the user's rule require a token per push).

### 7. Log and recovery

JSON lines in `${XDG_STATE_HOME:-~/.local/state}/claude-cleanup/cleanup.log`. Branch entries keep the tip commit id, so `git branch <name> <sha>` restores a branch. Worktree and scratchpad deletions cannot be undone, which is why clean and not-running checks are strict.

### 8. Skill shape

`plugins/base/skills/cleanup/SKILL.md` with `disable-model-invocation: true` (destructive, user invokes `/base:cleanup`). No `dependencies:` entry: it relies on no other skill, only on the `safety-guards.sh` hook, which the skill text names. The skill tells the model never to run `ls`, `find` or `du` on `/tmp` and to use only the script output.

## Real current state, example

Verified with `git worktree list`, `git branch -vv`, `gh pr list --state merged`, read-only. `origin/main` was fetched first.

| id | kind | item | why | class |
|----|------|------|-----|-------|
| b1 | local branch | `docs/plugin-readme-format` | PR #229 merged | safe |
| b2 | local branch | `feat/base-drop-playwright-mcp` | PR #233 merged | safe |
| b3 | local branch | `fix/base-claude-md-sync` | PR #238 merged | safe |
| b4 | local branch | `fix/setup-zsh-direct-start-resume` | PR #237 merged | safe |
| w1 | worktree + branch | `claude-marketplace.worktrees/fix-237-238`, `fix/review-237-238` | PR #239 merged, clean | safe |
| w2 | worktree + branch | `claude-marketplace.worktrees/push-gate`, `fix/push-gate-bypass` | PR #241 merged, clean | safe |
| w3 | worktree (detached) | `claude-marketplace.worktrees/reviews-237` at `a588d34` | commit in `origin/main`, clean | safe |
| w4 | worktree (detached) | `claude-marketplace.worktrees/reviews-238` at `ca79ad3` | commit in `origin/main`, clean | safe |
| r1..r8 | remote branch | `docs/plugin-readme-format`, `feat/base-drop-playwright-mcp`, `feat/review-browser-plugins`, `fix/base-claude-md-sync`, `fix/push-gate-bypass`, `fix/review-237-238`, `fix/setup-zsh-direct-start-resume`, `refactor/base-extras-layout` | PRs #229 #233 #221 #238 #241 #239 #237 #226 merged | safe, one push |
| s1 | scratchpads | 207 stale sessions with empty scratchpads | not running, older than 7 days | safe, grouped |
| s2..s4 | scratchpad | `d41c14aa` (292 days, 3.5 KB), `c31e2708` (66 days, 65 KB), `b1238b4d` (14 days, 20 MB) | not running, older than 7 days | safe, listed one by one |

Never listed:
- `chore/openspec-init` (primary checkout branch, PR #243 open).
- `chore/cleanup-rule` and its worktree (current work, no PR).
- `main`, the primary checkout and the 5 live sessions' scratchpads.
- The `release-please--branches--main--components--*` branches: all their PRs are merged but the bot reuses the names, so they are protected by default.

## Risks / Trade-offs

- [Squash merge with no `gh` or `glab`] is undetectable → reported as "needs gh or glab", never guessed.
- [`gh` rate limits or no auth] → fall back to checks 1 and 3 and print which check was skipped.
- [Session file missing for a live session] → age limit (7 days) bounds the risk; an active session touches its scratchpad.
- [Ignored files lost with a worktree, for example a local `.env`] → shown as a count of ignored files in the table, not blocking. See open questions.
- [macOS liveness is weaker] → fail safe: keep the folder when a pid exists.
- [Remote delete partially fails] → report git's message, no automatic retry, no second token without asking.
- [Plan goes stale between scan and remove] → each item is re-verified immediately before deleting.

## Open Questions

Assumptions made because the user could not be asked:

1. Scratchpad scope defaults to this repository's project folders, with `--all-projects` as opt-in. The user's words ("`/tmp/claude-<uid>/<project>/<session>/scratchpad`") do not say which.
2. Default age is 7 days. Changeable with `--days`.
3. On macOS the scratch root is assumed to be `/tmp/claude-<uid>`. If Claude Code uses `$TMPDIR` there, the script needs a second root; verify on a Mac in the task for macOS support.
4. `release-please--*` branches are protected by default. The user may prefer to delete them once their PR is merged.
5. Ignored files (for example `.env`) do not block worktree removal. A stricter rule would treat any ignored file outside build folders as risky.
6. The own-session group matches only `mktemp -d` shaped names. The user may want the whole current scratchpad offered at the end of a session.
7. Remote branch approval is part of the single dialog and counts as the "yes" for the push because the question says it is a push. If the user wants a second, separate confirmation per push, the skill needs one more question.
8. Only `origin` is handled. Other remotes (forks) are ignored.

# Spec Delta

## Purpose

Defines which leftovers the cleanup skill reports (merged branches, worktrees and scratch folders) and where it is allowed to look, so the scan is cheap and never wanders through unrelated files.

## ADDED Requirements

### Requirement: Scan reads known locations only
The scan SHALL inspect only the current repository (branches, remotes, worktrees), the folders `<repo>.worktrees/` and `<repo>-*` next to the primary checkout, and the Claude scratch root `/tmp/claude-<uid>/`. It MUST NOT search `/tmp`, `$HOME` or other paths.

#### Scenario: Unrelated files in /tmp
- **WHEN** `/tmp` holds folders that are not under `/tmp/claude-<uid>/`
- **THEN** the scan does not list, read or count them

#### Scenario: Scan changes nothing
- **WHEN** the user runs the scan
- **THEN** no branch, worktree or file is deleted and the only writes are the fetch of `origin` and the scan result file

### Requirement: Merge is judged against the remote default branch
A branch SHALL count as merged only when its tip is contained in `origin/<default>` after a fetch, or when a merged pull request or merge request has the same head commit as the branch tip, or when every commit of the branch has a patch-equivalent commit in `origin/<default>`. The local default branch MUST NOT be used as the reference.

#### Scenario: Regular merge
- **WHEN** a local branch tip is an ancestor of `origin/main`
- **THEN** the branch is listed as merged

#### Scenario: Squash merge with gh available
- **WHEN** a branch tip is not an ancestor of `origin/main` but a merged PR for that branch has the same head commit
- **THEN** the branch is listed as merged and the PR number is shown

#### Scenario: Rebase merge without a platform CLI
- **WHEN** `gh` and `glab` are unavailable and every commit of the branch has a patch-equivalent commit in `origin/main`
- **THEN** the branch is listed as merged

#### Scenario: Squash merge without a platform CLI
- **WHEN** `gh` and `glab` are unavailable and the branch was squash merged
- **THEN** the branch is not listed and the output says that squash merges need `gh` or `glab`

#### Scenario: Branch reused after its PR merged
- **WHEN** a branch has commits that are not in the merged PR head and not in `origin/main`
- **THEN** the branch is listed as having unmerged commits and is not selected by default

#### Scenario: Stale local default branch
- **WHEN** local `main` is behind `origin/main`
- **THEN** merged status is still computed against `origin/main`

### Requirement: Local branches
The scan SHALL list merged local branches. It MUST skip the default branch, the branch checked out in the primary checkout, the branch checked out in the current worktree and branches matching a protected pattern (default `main`, `master`, `develop`, `trunk`, `release/*`, `release-please--*`).

#### Scenario: Current branch is merged
- **WHEN** the current branch is merged into `origin/main`
- **THEN** it is not listed

#### Scenario: Branch of an open PR
- **WHEN** a branch has an open PR and is not contained in `origin/main`
- **THEN** it is not listed

### Requirement: Remote branches
The scan SHALL list branches on `origin` that satisfy the merged rule, excluding the default branch and protected patterns. Each entry MUST show the pull request number when known.

#### Scenario: Merged remote branch
- **WHEN** `origin/fix/push-gate-bypass` is contained in `origin/main`
- **THEN** it is listed under remote branches with its PR number

#### Scenario: Bot branch
- **WHEN** a branch matches `release-please--*`
- **THEN** it is not listed unless the user passes a different protect list

### Requirement: Worktrees
The scan SHALL list a linked worktree when its branch counts as merged, or when it is detached and its commit is contained in `origin/<default>`. The primary checkout, the current worktree, locked worktrees and worktrees used as the working directory of a running Claude session MUST NOT be listed as removable. A worktree whose folder is gone SHALL be listed as dangling.

#### Scenario: Clean worktree of merged work
- **WHEN** a linked worktree has a merged branch, no uncommitted changes, no untracked files and no unpushed commits
- **THEN** it is listed as safe

#### Scenario: Worktree with changes
- **WHEN** a linked worktree of a merged branch has uncommitted changes, untracked files or commits not in the merged head
- **THEN** it is listed as risky with the dirty file count and the commit count

#### Scenario: Worktree in use
- **WHEN** a running Claude session has a worktree as its working directory
- **THEN** the worktree is not removable and the output names the session

#### Scenario: Dangling worktree entry
- **WHEN** git still records a linked worktree whose folder no longer exists
- **THEN** it is listed as dangling and removing it only prunes the git record

### Requirement: Orphan worktree folders
The scan SHALL inspect direct children of `<repo>.worktrees/` and sibling folders named `<repo>-*` that git does not list as worktrees. A folder SHALL be listed as an orphan only when its `.git` is a file pointing into this repository's `.git/worktrees/` and that target is missing. Any other unregistered folder MUST be reported as unknown and never deleted.

#### Scenario: Sibling that is another repository
- **WHEN** `<repo>-backend` has a `.git` directory
- **THEN** it is reported as unknown and is not a candidate

#### Scenario: Orphan folder
- **WHEN** a folder under `<repo>.worktrees/` has a `.git` file pointing to a missing `worktrees/<name>` entry
- **THEN** it is listed as an orphan and marked risky because its changes cannot be checked

### Requirement: Scratchpads of sessions that are not running
The scan SHALL list session folders under `/tmp/claude-<uid>/<project>/<session>/` when the session is not running and the newest file in the folder is older than N days (default 7). A session is running when a file in `~/.claude/sessions/` names it, its process id exists and, where the platform exposes it, its recorded start time matches.

#### Scenario: Running session
- **WHEN** a session file names a live process with matching start time
- **THEN** its folder is never listed

#### Scenario: Reused process id
- **WHEN** a session file names a process id that now belongs to a different process
- **THEN** the session counts as not running

#### Scenario: Recent scratch
- **WHEN** a session is not running but a file in its folder changed less than N days ago
- **THEN** the folder is not listed

#### Scenario: No session file
- **WHEN** no session file names the session and the folder is older than N days
- **THEN** the folder is listed

#### Scenario: Empty scratchpads
- **WHEN** many stale session folders are empty
- **THEN** they are shown as one grouped entry with a count, and non-empty ones are listed one by one with size and file count

#### Scenario: Symlink inside a scratchpad
- **WHEN** a scratchpad contains a symlink to a path outside the scratch root
- **THEN** only the link is removed and its target is left alone

### Requirement: Scratch scope is this repository by default
The scan SHALL read only the project folders under the scratch root that belong to this repository (its path, its worktrees and its subfolders). The option `--all-projects` SHALL widen the scan to every project folder under the scratch root.

#### Scenario: Other project
- **WHEN** a stale scratchpad belongs to another project and `--all-projects` is not given
- **THEN** it is not listed

#### Scenario: All projects
- **WHEN** the user passes `--all-projects`
- **THEN** stale scratchpads of every project under the scratch root are listed

### Requirement: Own session leftovers first
When given the current session's scratchpad path, the scan SHALL list the folders in it that match the shape `mktemp -d` produces (`tmp.<random>` or a name ending in a random suffix of at least six characters) and show them as a separate group before all other candidates. It MUST NOT list plain files or other folders there, and it MUST NOT list the current working directory.

#### Scenario: Agent forgot its mktemp folder
- **WHEN** the current scratchpad contains `tmp.Ab12Cd34Ef`
- **THEN** it is listed first as the session's own leftover, with no age limit

#### Scenario: Report file in the scratchpad
- **WHEN** the current scratchpad contains `notes.md` or a folder named `explore`
- **THEN** neither is listed

### Requirement: Compact output
The scan SHALL print one table of at most about 40 lines for typical use, grouped by kind, with a stable short id per item, and a one-line summary of counts. It MUST NOT print file contents.

#### Scenario: Nothing to clean
- **WHEN** the scan finds no candidates
- **THEN** it prints one line saying so and exits with status 0

#### Scenario: Large state
- **WHEN** more than 40 items would be printed
- **THEN** the table shows the oldest or largest first, the rest are counted in a summary line and all of them stay in the scan result file

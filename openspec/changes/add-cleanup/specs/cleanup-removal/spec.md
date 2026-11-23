# Spec Delta

## Purpose

Defines how the cleanup skill gets approval, what it refuses to delete, how remote branch deletes pass the push gate and how removals are logged, so cleanup stays safe without slowing the user down.

## ADDED Requirements

### Requirement: Dry run by default
The script SHALL delete nothing unless it is called with an explicit apply flag. Without the flag it prints what it would do for the given ids.

#### Scenario: Removal without apply flag
- **WHEN** the remove command is called with ids but no apply flag
- **THEN** it prints the planned actions and deletes nothing

#### Scenario: Scan only
- **WHEN** the user invokes `/base:cleanup` and answers no to the question
- **THEN** nothing has been deleted

### Requirement: One approval step with deselection
The skill SHALL show the candidate list once and ask once with AskUserQuestion. The user MUST be able to approve all safe items, approve all except named ids, or cancel. Items marked risky MUST be excluded from "approve all".

#### Scenario: Approve all safe items
- **WHEN** the user picks "delete all listed"
- **THEN** every safe local item is removed and no risky item is touched

#### Scenario: Deselect some items
- **WHEN** the user names ids to keep
- **THEN** those ids are not removed and all other safe items are

#### Scenario: Long list
- **WHEN** the list has more items than a dialog can hold as options
- **THEN** the skill shows the numbered table in text and uses the dialog for the choice, with ids to keep entered as free text

### Requirement: Risky items need their own yes
A worktree with uncommitted changes, untracked files or unpushed commits, a branch with commits outside the merged head, an orphan worktree folder, a worktree with an ignored file that differs from the primary checkout and a stale session folder holding any regular file other than `started` SHALL be removed only after a separate explicit yes for that item. The question MUST name what would be lost (changed files and commit subjects, capped).

#### Scenario: Dirty worktree
- **WHEN** a worktree of a merged branch has 3 changed files
- **THEN** the skill asks about that worktree alone, lists the files and removes it only on yes

#### Scenario: Commits after the merged PR
- **WHEN** a branch has 7 commits after its merged PR
- **THEN** the question names the first 5 commit subjects and "and 2 more"

#### Scenario: Stale session folder with files
- **WHEN** the user approves all safe items and a stale session folder holds 65 KB of files in `scratchpad/` or `tasks/`
- **THEN** it is not removed with the safe group; the skill asks about it alone, naming its size and newest files

#### Scenario: User declines a risky item
- **WHEN** the user answers no for a risky item
- **THEN** the worktree and its branch are kept and the run continues with the next item

### Requirement: Protected targets
The script MUST NOT delete the primary checkout, the default branch, the branch checked out in the primary checkout, the current worktree, its branch, or any path outside the known locations. It MUST re-check each item immediately before deleting it and skip the item if the condition no longer holds.

#### Scenario: State changed after the scan
- **WHEN** a worktree became dirty between the scan and the removal
- **THEN** it is skipped as changed and reported

#### Scenario: Path escapes the scratch root
- **WHEN** a session folder path resolves outside `/tmp/claude-<uid>/`
- **THEN** it is refused

#### Scenario: Branch checked out elsewhere
- **WHEN** a merged branch is checked out in a worktree that is not being removed
- **THEN** the branch is not deleted

### Requirement: Safe removal commands
Worktrees SHALL be removed with `git worktree remove`, forced only for a risky worktree that got its own yes and is unchanged since the scan. Safe items and items without their own yes MUST NOT be forced. A worktree and its merged branch SHALL be removed together, worktree first. Local branches SHALL be deleted only after the merged check, with the tip commit written to the log. A session folder SHALL be removed as the whole `<session>/` folder without following symlinks.

#### Scenario: Git refuses the removal
- **WHEN** `git worktree remove` fails for a safe worktree
- **THEN** the item is reported as skipped with git's message and nothing is forced

#### Scenario: Approved dirty worktree
- **WHEN** the user says yes to a dirty worktree of merged work and it is unchanged since the scan
- **THEN** it is removed with `git worktree remove --force`

#### Scenario: Approved dirty worktree changed again
- **WHEN** a dirty worktree got its yes but has new changes since the scan
- **THEN** it is skipped as changed and nothing is forced

#### Scenario: Worktree plus branch
- **WHEN** a clean merged worktree is approved
- **THEN** the worktree folder is removed and then its local branch is deleted

#### Scenario: Session folder removed
- **WHEN** an empty stale session folder is approved
- **THEN** the whole `<session>/` folder is deleted, including `scratchpad/`, `tasks/` and `started`

### Requirement: Remote branch deletes pass the push gate
The script SHALL never push. Approved remote branch deletions SHALL be run by the skill as one `git -C <primary checkout> push origin --delete <branches>` command, after the user approved the remote group and its question stated that it is a push. The skill MUST create the push token in its own call before that command, as the safety-guards hook demands, and MUST NOT use any other way to delete remote branches.

#### Scenario: Remote group approved
- **WHEN** the user approves 5 remote branches
- **THEN** the skill creates the token, runs one push with all 5 branches and the hook consumes the token

#### Scenario: Remote group not approved
- **WHEN** the user keeps all remote branches or does not answer the remote question
- **THEN** no push command is run and no token is created

#### Scenario: Push fails for one branch
- **WHEN** one remote branch is already gone or protected
- **THEN** the skill reports git's message and does not retry with a second token without asking

### Requirement: Removal log
Every removal and every skipped item SHALL be appended as one JSON line to `${XDG_STATE_HOME:-~/.local/state}/claude-cleanup/cleanup.log` with time, kind, target and result. Branch entries MUST include the tip commit id so the branch can be recreated. Approved remote branches MUST be logged with their tips before the push runs.

#### Scenario: Branch deleted
- **WHEN** a local branch is deleted
- **THEN** the log line holds the branch name and its tip commit id

#### Scenario: Remote branches approved
- **WHEN** the user approves 2 remote branches
- **THEN** the script writes one log line per branch with its tip before the skill runs the push

#### Scenario: Log summary
- **WHEN** a removal run ends
- **THEN** the skill prints counts of removed, skipped and failed items and the log path

### Requirement: Platform support
The script SHALL run on Linux, WSL and macOS with Python 3 and git only. Where session liveness cannot be proven, a session SHALL be treated as running.

#### Scenario: macOS session check
- **WHEN** the platform has no `/proc` and the recorded process id exists
- **THEN** the session counts as running and its session folder is kept

#### Scenario: No gh and no glab
- **WHEN** neither CLI is installed
- **THEN** the scan still runs using the ancestor and patch-equivalence checks and says which checks were skipped

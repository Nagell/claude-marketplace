---
name: cleanup
description: Find and remove leftovers of finished work in the current repository. Lists merged local and remote branches, worktrees of merged work that are clean and pushed, orphan worktree folders, scratch folders of Claude sessions that are no longer running and the current session's own forgotten mktemp folders. One script does the scanning and deleting, so the run costs few tokens. Shows one table, asks once, asks again for each risky item, deletes only what you approved and logs every removal. Remote branch deletes run as one push through the push token gate. Invoke only via /base:cleanup.
argument-hint: "[--all-projects] [--days N]"
disable-model-invocation: true
---

# Cleanup

A safety net for leftovers: merged branches, worktrees of finished work and scratch folders of sessions that stopped. The rule that each agent deletes its own scratch work still holds. This skill catches what slipped through.

`$SKILL_DIR` is the folder this SKILL.md was loaded from. `$SCRIPT` is `$SKILL_DIR/scripts/cleanup.py`. `<scratchpad>` is the session scratchpad named in your system prompt.

## Rules

- Use only the script's output. Never run `ls`, `find`, `du` or `stat` on `/tmp`, `$HOME` or the scratch folders. Exploring there costs tokens and is what this skill avoids.
- The script deletes nothing without `--apply`. Run `remove` with `--apply` only with ids the user approved in this run.
- The script never pushes. Remote branches are deleted by you, with one `git push` that passes the `safety-guards.sh` push token gate (step 5).
- Never pass `--force` to anything and never delete a listed path yourself. If the script skips an item, report it and move on.

## Steps

### 1. Scan

Run from the repository the user is working in:

```bash
python3 $SCRIPT scan --own <scratchpad> [--all-projects] [--days N]
```

Pass `--all-projects` and `--days` only when the user gave them. Show the table exactly as printed. If it prints `Nothing to clean.`, say so and stop.

Classes in the table:

- `safe`: provably merged and clean, or an empty session folder. Covered by the single question.
- `risky`: something would be lost (changed files, commits after the merged PR, ignored files missing in the primary checkout, an orphan worktree folder or a session folder that still holds files). Each needs its own yes.

### 2. One question for all safe items

Ask one AskUserQuestion with up to two questions:

1. Local items (ids `m`, `b`, `w`, `o`, `s` marked safe). Options: "Delete all safe items (Recommended)", "Delete all safe items except some" (the user types the ids to keep in the free-text answer), "Cancel".
2. Only when the table has `r` items: "Delete these N remote branches on origin? This is a git push." Options: "Yes, push the deletes", "No, keep them". Name the branches in the question. A yes here is the user's yes for that one push.

The table carries the ids. Do not try to list every item as an option. On "Cancel" stop: nothing has been deleted.

### 3. Risky items, one by one

For each risky item, ask one question (up to four per AskUserQuestion call). Name what would be lost, using the `why` text from the table: the files, the commit count or the size and newest files. Options: "Keep it (Recommended)", "Delete it". A "Keep" or no answer keeps the item. Skip this step when the user cancelled in step 2.

### 4. Remove

```bash
python3 $SCRIPT remove --ids <approved safe ids> --allow-risky <approved risky ids> --apply
```

Leave out ids the user kept. Leave out `r` ids here; step 5 handles them. The script checks each item again right before it deletes it, removes a worktree before its branch and never forces `git worktree remove`. Relay its last line (removed, skipped and failed counts and the log path) and any `Skipped` or `Failed` lines.

### 5. Remote branches, only after a yes in step 2

The push token gate in `safety-guards.sh` reads the command text, so this push must be run by you, never by a script.

1. In its own Bash call: `touch <primary checkout>/.claude-push-token`
2. In the next Bash call: `git -C <primary checkout> push origin --delete <branch> <branch> ...`

The primary checkout is the path in the first line of the scan table. Use one push for all approved remote branches and one token for that push. If git reports an error for a branch, relay git's message. Do not retry and do not create a second token without asking the user again.

If the user said no, or did not answer, create no token and run no push.

## Recovery

Each removal is one JSON line in `${XDG_STATE_HOME:-~/.local/state}/claude-cleanup/cleanup.log`. Branch lines hold the tip commit, so `git branch <name> <sha>` restores a branch. Removed worktrees and folders cannot be restored, which is why the checks are strict.

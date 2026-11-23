---
name: resolve-review
description: The author's side of a code review. Run it on your own branch after reviewers have commented on its GitLab merge request or GitHub pull request. It finds the MR for the branch, reads the unresolved threads, checks each one against the code at the branch head (already addressed, needs a fix, disagree, or a question to answer), and shows a resolution plan with every draft reply in full. Only after you approve does it make the fixes (committing nothing unless asked), post the replies in your voice and resolve the threads you chose. Use when the user asks to answer, address or resolve the review comments on their own MR or PR, or runs /base:resolve-review.
argument-hint: "[<mr-or-pr-url | !iid | #number>]"
dependencies:
  - writing-style-guide
  - humanizer
  - review-mr
---

# Resolve the review on your own MR

The counterpart to `review-mr`: there you review someone else's MR, here you
answer the review on yours. "MR" means a GitLab merge request or a GitHub pull
request. Nothing is changed, posted or resolved until the user has seen the plan
and every reply that would go out.

The skill rests on one habit: **judge a comment by the code as it is now.**
Reviewers comment on an old head; by the time the author answers, some findings
are fixed, lines have moved, and some comments were wrong from the start. Skip
the check and the plan redoes finished work or tells a reviewer "fixed" when it
isn't.

## How this skill is built

- **Core** - this file: finding the MR, judging the threads, the plan, fixes,
  replies and resolving.
- **Scripts** - `gitlab_comments.py`, `github_comments.py` and `find_rules.py`
  from `$SKILL_DIR/../review-mr/scripts/`, so both sides of a review share one
  tested client per platform. `../review-mr/platforms/<platform>.md` explains
  thread ids and how each platform treats replies and resolving.
- **Project rules** - `~/.claude/review-rules/<repo>.md`, the same files
  `review-mr` reads.
- **Voice** - `writing-style-guide` and `humanizer`, when installed.

`$SKILL_DIR` is the directory this file was loaded from, `$SCRATCH` the
session's scratchpad, and `$SCRIPT` the platform's script. Every `$SCRIPT` call
takes `--project` (GitLab: numeric id or URL-encoded path; GitHub:
`owner/repo`) and, except `for-branch`, `--iid` (MR iid or PR number).

## 0. Platform and project rules

Read the platform off the MR URL the user passed, or else off
`git remote get-url origin`: `github.com` is GitHub, `gitlab` in the host is
GitLab, and a rules file may set `Platform:` for a self-hosted host. Take
`--project` from the same URL. The rules' machine notes say how to run `gh` or
`glab` where a sandbox hides the token or a per-folder config picks the account.

```bash
python3 $SKILL_DIR/../review-mr/scripts/find_rules.py
```

Run inside the checkout, it names the repo from the remote. Read the rules file
whole when `path` is set, for the repo's conventions, test commands and machine
notes; mention any `skipped` entry in one line, since a typo in a rules file
reads like "no rules". When `path` is `null`, show this and carry on:

```text
────────────────────────────────────────────────────────────────────
 No review rules for <repo>
 Looked for: <expected>
 A rules file there (or any *.md in ~/.claude/review-rules/ whose
 frontmatter lists <repo> under applies-to:) adds the repo's
 conventions, test commands and machine notes. Continuing
 without rules.
────────────────────────────────────────────────────────────────────
```

## 1. Find the MR

A URL or id the user passed wins. Otherwise:

```bash
python3 $SCRIPT --project <project> for-branch --branch "$(git branch --show-current)"
```

It lists every MR on that branch, open ones first, with state and author.

- **One open MR** - use it.
- **Several open** - ask which, once.
- **Only merged or closed** - say so and ask whether to go on; any fix then
  belongs on a new branch.
- **None** - the branch may not be pushed yet; stop and say so.

Then read its head and title:

```bash
python3 $SCRIPT --project <project> --iid <iid> refs
```

## 2. Fetch the open threads

```bash
python3 $SCRIPT --project <project> --iid <iid> threads --unresolved \
  --out $SCRATCH/threads.json
```

Each thread carries its full conversation (`notes`), who opened it, the
`path`, the `new_line` and `head_sha` it was written against, and `me`, the
logged-in user. Without `--unresolved` you also get general comments and
review summaries; read those once for questions that need an answer, since a
reviewer sometimes asks something in the summary only.

**Bots.** Leave out a bot's summaries and walkthroughs: they restate the MR. An
account is a bot when its name ends in `[bot]` or `-bot`, matches GitLab's
token users (`project_<id>_bot...`, `group_<id>_bot...`), or is a known service
(`coderabbitai`, `github-actions`, `dependabot`, `sonarcloud`, `codecov`,
`renovate`). A bot's inline finding is still a thread: judge it like any other.

**Already answered.** When the last note is from `me` and says the point is
handled (a commit link, "done", a reasoned reply), the thread is waiting on the
reviewer, not on the author. Still check the claim against the code, but plan
no new reply unless the check contradicts it.

No open threads left: say so and stop.

## 3. Judge each thread against the code at the branch head

Work in the user's checkout. Compare `git rev-parse HEAD` with the `head_sha`
`refs` printed, after `git fetch`:

- equal - judge at that head;
- local is ahead (unpushed commits) - judge at local `HEAD`, and mark any fix
  that lives only in those commits, since the reviewer cannot see it yet;
- local is behind or on another branch - ask before switching or pulling,
  because the user may have work in progress.

Read files with `git show <sha>:<path>` rather than from the working tree, so
uncommitted edits do not pass for a fix. Note uncommitted changes that touch a
thread, though: they are usually a fix in progress.

**Find the code by content, not by line number.** The thread's line points into
the head it was written on. Look up what the comment talks about (the function,
the condition, the sentence) at the current head. A line that happens to still
match is how a stale verdict slips through.

To find what changed since the comment, run
`git log --oneline <thread head_sha>..<head> -- <path>` and read the commits
that touch the code in question. A thread with no `head_sha` (a general
comment) gets `git log` over the MR's range.

Each thread gets one verdict:

| verdict      | when                                                       | evidence to give                                          |
| ------------ | ---------------------------------------------------------- | --------------------------------------------------------- |
| **Addressed** | the code at head already does what the reviewer asked, or the problem is gone | the commit (short sha) and `file:line` at head |
| **Fix**      | the point stands at head and is right                      | `file:line` and the change you would make                 |
| **Disagree** | the point stands but the code is right, or the cost outweighs it | the reason, from the code: a caller, a test, a constraint |
| **Answer**   | the reviewer asks a question rather than asking for a change | the answer, with `file:line` where it helps            |

A thread can hold several points (a reviewer's "lows" thread, say). Judge each
point, give the thread the verdict of its weakest one, and name the points still
open. A finding the code cannot settle (it depends on a production setting, or
on behaviour you would have to run) is marked unsettled, not guessed.

For more than about eight threads, split the judging across a few read-only
agents grouped by file, each given the thread JSON, the head sha and this step.

## 4. The resolution plan

Write the plan to `$SCRATCH/resolve-plan.md` and print it in the reply. Number
the threads `R1`, `R2`, ... in file order and keep those ids for the rest of
the run. Per thread:

```markdown
### R3 - Addressed - `scripts/client.py:812`
Thread: <link> (opened by <reviewer>)

<The reviewer's point in one or two plain sentences, so the user need not
open the thread.>

**Verdict.** Fixed in `0dc4655`: `discard-drafts` now empties the ledger
(`scripts/client.py:891`).
**Planned change.** None.
**Draft reply.**
> Fixed in [`0dc4655`](<commit url>).
```

Above the threads, one line of totals per verdict. Where no reply is planned
(already answered, or the user's own thread with nothing to add), the draft
reply says `none` and why.

**Draft replies.** They go out in the user's name, so write them the way the
user writes: run them through **writing-style-guide** (which pulls in
**humanizer**) when installed. Without them:

- **Addressed or Fix** - the commit link, and a `file:line` when the fix sits
  somewhere the reviewer would not look. Nothing else: the reviewer opens the
  commit faster than they read about it.
- **Disagree** - two or three sentences with the reason from the code, and room
  for them to push back. No apology, no "great point".
- **Answer** - the answer first, then the `file:line` that shows it.
- A reply never claims a fix the reviewer cannot see. A fix made in this run, or
  sitting in an unpushed commit, gets its commit link only once it is pushed
  (step 6).

Then ask, in the same turn as the printed plan, with **AskUserQuestion**. The
dialog can hide what sits above it, so put the plan (or, when it is too long,
the one-line-per-thread list and the plan's full path) in the recommended
option's `preview`. Two questions:

1. **The plan** - post every reply and make every fix as drafted
   (recommended); or change some (the user names ids and gives the edit); or
   stop here.
2. **Resolving** - `Leave resolving to the reviewer` (recommended: many teams
   expect a reviewer to close their own thread once they have checked the
   answer); `Resolve the threads I addressed` (Addressed and Fix, once their
   reply is up); `Choose per thread`, then ask once more with the ids.

When every open thread is the user's own (a self-review), recommend
`Resolve the threads I addressed` instead: there is no other reviewer to wait
for. `Resolve the threads I addressed` never covers Disagree or Answer threads: the
reviewer has not had their say on those yet.

Apply every edit the user makes to a reply word for word, then show the changed
reply once more before it posts.

## 5. Make the fixes

Only for Fix threads the user kept. Change the code, run the tests the rules or
the repo name for the touched area, and show the diff with one line per thread
saying which hunk answers it. Commit nothing unless the user asks; when they do,
one commit per concern, with the repo's commit convention, and pathspec commits
so nothing unrelated rides along. A fix that turns out wrong or larger than
planned goes back to the user before its reply is posted.

## 6. Post the replies

Check first that what each reply cites is visible on the MR: a commit it links
must be in the MR head (re-run `refs` and test with
`git merge-base --is-ancestor <sha> <head_sha>`). Hold any reply that fails
this and tell the user which ones wait for a push; post the rest.

```bash
python3 $SCRIPT --project <project> --iid <iid> reply \
  --discussion <discussion_id> --file $SCRATCH/r3.md
```

Take the `discussion_id` whole from `threads.json`. On GitHub a general comment
(`issuecomment-...`) or review summary has no thread: answer it with `note`
and quote the line you answer. Replies post one by one, not as a review, so each
reviewer sees the answer on their own thread.

After a failed post, check a fresh `threads` dump before retrying: a 5xx often
lands anyway, and a blind retry double-posts.

## 7. Resolve

Only the threads the user chose in step 4, and only after their reply landed:

```bash
python3 $SCRIPT --project <project> --iid <iid> resolve --discussion <id>
python3 $SCRIPT --project <project> --iid <iid> resolve --discussion <id> --as-author
```

The plain form works on threads the user opened. A reviewer's thread needs
`--as-author`, which the script refuses unless the user opened the MR: on
someone else's MR, closing a reviewer's thread is not the user's call. This
skill never reopens a thread.

Finish with one line per thread: replied, resolved, held for a push, or left as
it was, and the fixes left uncommitted.

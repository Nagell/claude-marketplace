# GitLab

How the review steps in `SKILL.md` run on a GitLab merge request.

- `$SCRIPT` is `$SKILL_DIR/scripts/gitlab_comments.py`. It wraps `glab api`, so
  `glab` must be installed and logged in. The rules' machine notes say how to
  run it where a sandbox hides the token.
- `--project` is the numeric project id or the URL-encoded project path
  (`group%2Fsub%2Frepo`); `--iid` is the `!123` number.
- When a glab helper skill is installed (the rules may name one), use it for
  glab mechanics beyond what the script covers.

## Fetching the MR

`refs` prints GitLab's `diff_refs`: `base_sha` is the merge-base GitLab itself
diffed against, `start_sha` the target branch tip, `head_sha` the MR head, and
the source and target branch. In the reviews worktree:

```bash
git -C <worktree> fetch origin <source_branch>
git -C <worktree> checkout --detach <head_sha>
```

For an MR from a fork, `fetch origin refs/merge-requests/<iid>/head` brings the
head in instead.

`diff` and `added-lines` read `/merge_requests/<iid>/diffs`, every page of it.
`/changes` collapses a large file's diff to an empty string, which reads exactly
like "nothing changed here". A diff GitLab withholds as too large is flagged in
`refs` and `diff` and on stderr; the rest of the MR stays reviewable, and only
an inline anchor on that file is refused (use `--outside`).

## The counterpart

`counterpart --sibling <project id>` lists every open MR in the sibling project
on the same source branch, plus MRs the description links as
`<sibling path>/-/merge_requests/<n>` or `<sibling path>!<n>`, each with its
url, branch, `base_sha`, `head_sha` and draft state.

In contract scope, read the counterpart's files at its head through the API:

```bash
glab api "projects/<cp_project>/repository/files/<url-encoded path>/raw?ref=<cp_head_sha>"
```

## Threads

`threads` dumps every discussion with a human note. "Ours" means the first
non-system note was written by the user `glab` is logged in as (`me`).
`severity` is parsed from the first line of that note, `head_sha` and
`new_line` come from the note's position, which keeps the sha it was written
against. General notes and review summaries appear as non-resolvable threads.
`--unresolved` keeps only resolvable threads that are still open.

For the author's side (the `resolve-review` skill): `for-branch --branch <name>`
lists the MRs on a source branch and needs no `--iid`, and
`resolve --as-author` resolves a reviewer's thread, refused unless `me` opened
the MR.

## Anchors

An inline thread carries a `position` object (`base_sha`, `start_sha`,
`head_sha`, paths, line). `glab api -f`/`-F` build a flat JSON body and silently
drop the nested `position`, which turns an inline thread into an unanchored
general note; the script sends the body through `--input` instead and checks
that the anchor came back populated.

- An added line anchors with `new_line` alone; a context line needs `old_line`
  as well. The script works this out from the diff.
- A span goes out as a `line_range` with both endpoints and anchors on its end
  line. A span that runs past the diff is clamped to the part inside and the
  script says so. It refuses a clamped span whose body holds a suggestion fence
  (the offsets count from the new end line and would hit lines above the
  span), and a span that crosses from one hunk into the next.
- `draft --outside path:40-47` drafts a general note in the same review, opened
  with `**Outside the diff - `path:40-47`**`, and turns a suggestion fence into a
  plain code sample.

**Suggestion fences.** GitLab places a suggestion relative to the line the
thread anchors on, which is the span's end line. Use `suggestion:-N+0` with
`N = end - start`, or plain `suggestion` on a single line. GitLab caps the
offsets at 100, so a longer span gets prose instead. It renders as a diff with
an **Apply suggestion** button.

## Drafts and the review

A draft is a GitLab **draft note**: visible only to its author until the
review is submitted. `submit` calls `draft_notes/bulk_publish` with a
`reviewer_state`, which publishes every pending draft the user holds on the MR
at once, including any they wrote by hand.

- **Replies and `--resolve`.** GitLab reopens a thread when a draft reply
  without `resolve_discussion` is published
  (`DraftNotes::PublishService#set_discussion_resolve_status`). So every closing
  reply carries `--resolve`, and `draft` refuses a reply on a resolved thread
  without `--resolve`, unless `--reopen` says reopening is the point.
- Where GitLab refuses `resolve_discussion` on the draft, `draft` creates it
  without, records the resolve in the ledger, and `submit` resolves the thread
  directly afterwards.
- A draft GitLab returns without its anchor is deleted and reported.
- A reopen is a draft reply with `--reopen`: publishing it reopens the thread.
  Like `--resolve`, it is refused on a thread we did not open.

**Verdict.** `--state requested_changes` holds the merge until we re-review;
`--state reviewed` is GitLab's **Comment**. The summary note (`--file`) is
optional. `bulk_publish` answers 204 even when the state change did not stick,
so `submit` reads back how many drafts published, the reviewer state from
`/reviewers` and whether the summary note shows on the MR. Any other answer
from `bulk_publish` is an error, and `submit` stops on it. A successful `submit`
empties the ledger, and so does `discard-drafts`.

**Approval.** `approve --sha <head_sha>` sends the reviewed sha, and GitLab
refuses the approval when the author pushed since. It is a separate call after
the submit.

**General note.** `note` posts a general MR note for the finish-mode comment.
It must not be resolvable, or it blocks a merge under "all threads must be
resolved" and the approval next to it means nothing; the script fails if GitLab
made it resolvable.

**Errors.** GitLab throws 502s mid-run, and the write often lands anyway. On
any non-JSON response, run `drafts` or `threads` before retrying.

**Editing.** `edit --discussion <id> --note <id>` replaces a note's body and
keeps its anchor and replies. Discussion ids are long hex strings: take the
whole one from `threads`.

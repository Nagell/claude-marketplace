# GitHub

How the review steps in `SKILL.md` run on a GitHub pull request.

- `$SCRIPT` is `$SKILL_DIR/scripts/github_comments.py`. It wraps `gh api` (REST)
  and `gh api graphql`, so `gh` must be installed and logged in with access to
  the repo. The rules' machine notes say how to run it where a sandbox hides the
  token or a per-folder config picks the account.
- `--project` is `owner/repo`; `--iid` is the PR number.
- The subcommands, flags and output match `gitlab_comments.py`. The differences
  below are the places where GitHub works another way.

## Fetching the PR

`refs` prints the same four lines as on GitLab. `base_sha` is the merge base of
the base branch tip and the head (from the compare API), which is what the PR's
"Files changed" diff is taken against; `start_sha` is the base branch tip;
`head_sha` the PR head. In the reviews worktree:

```bash
git -C <worktree> fetch origin pull/<number>/head
git -C <worktree> checkout --detach <head_sha>
```

`pull/<number>/head` works for a PR from a fork too, where the branch is not in
`origin`.

`diff` and `added-lines` read `/pulls/<number>/files`, every page. A file whose
patch GitHub withholds although lines changed (too large) is flagged in `refs`
and `diff` and on stderr; the rest of the PR stays reviewable, and only an
inline anchor on that file is refused (use `--outside`). Binary files come
through with an empty diff. GitHub lists at most 3000 files
per PR.

## The counterpart

`counterpart --sibling <owner/repo>` lists every open PR in the sibling repo
whose head is the same `<owner>:<branch>`, plus PRs the description links as
`github.com/<sibling>/pull/<n>` or `<sibling>#<n>`, each with its url, branch,
merge-base `base_sha`, `head_sha` and draft state. A PR from a fork pairs only
with a sibling PR from the same fork owner.

In contract scope, read the counterpart's files at its head through the API:

```bash
gh api "repos/<cp_owner>/<cp_repo>/contents/<path>?ref=<cp_head_sha>" \
  -H "Accept: application/vnd.github.raw"
```

## Threads

`threads` prints the same JSON shape as on GitLab. Differences:

- A review thread's `discussion_id` is its GraphQL node id (`PRRT_...`). Take it
  whole from `threads`; every thread-level subcommand needs it. The id is
  global, so the script refuses one whose thread belongs to another PR.
- General PR comments appear as `issuecomment-<id>` and submitted review
  summaries as `review-<id>`, both with `resolvable: false`. Neither can be
  resolved, and a reply to one is a new general comment (`note`).
- `head_sha` and `new_line` come from the first comment's original commit and
  original line, the point it was written against.

## Anchors

A thread anchors with `line` (the end line) and `side: RIGHT`, plus
`startLine`/`startSide` for a span. GitHub accepts any line inside a hunk on the
new side, added or context, and rejects a line outside the hunks; the script
clamps a span to the part inside and says so, the same as on GitLab. It refuses
a span that crosses from one hunk into the next, and a clamped span whose body
holds a suggestion fence.

`draft --outside path:40-47`:

- on a file the PR changes: a **file-level comment** on that file, opened with
  `**Outside the diff - `path:40-47`**`;
- on a file the PR does not touch: GitHub has no anchor for it, so the ledger
  keeps the text and `submit` adds it to the review body.

A draft with no location at all (a general thread on GitLab) also goes into the
review body. The lows thread therefore anchors on a changed line whenever any
low sits in the diff.

**Suggestion fences.** A plain ```` ```suggestion ```` fence replaces exactly the
anchored span, from `startLine` to `line`. There are no `-N+M` offsets; write
the replacement for the whole span. It renders as a diff with a **Commit
suggestion** button.

## Drafts and the review

A draft is a comment in the viewer's **pending review**. GitHub allows one
pending review per user per PR and shows it only to its author.

- `draft` creates the pending review on the first draft, at the PR head, and
  records it in the ledger. If the user already holds a pending review with
  comments or a body this run did not write, `draft` refuses: those would be
  published with ours.
- **Replies and `--resolve`.** Publishing a reply never changes a thread's
  resolved state on GitHub, so nothing reopens by accident and `draft` does not
  refuse a reply on a resolved thread. `--resolve` is recorded in the ledger and
  `submit` resolves the thread after publishing (`resolveReviewThread`);
  `--reopen` likewise unresolves it after publishing (`unresolveReviewThread`).
  Both refuse a thread we did not open.
- A thread GitHub returns without a line is deleted and reported.
- `unresolve --discussion <PRRT_...>` reopens a thread right away. The thread
  must be ours.

**Verdict.** `submit` maps `--state` to the review event:
`requested_changes` → **Request changes**, `reviewed` → **Comment**,
`approved` → **Approve**. GitHub does not hold a merge on Request changes by
itself; only branch protection that requires approvals does. The script
requires a review body (`--file`, plus any unanchored drafts) for
`requested_changes`, which GitHub's API documents as required for that event,
so pass one line on what blocks. GitHub refuses Request changes and Approve on the
user's own PR, so `submit` refuses both there before publishing anything;
submit as `reviewed` instead.

`submit` reads back how many drafts left the pending state and the state of the
submitted review.

**Approval.** GitHub would record an approval against a stale sha, so
`approve --sha <head_sha>` refuses when the PR head moved, then submits an
Approve review at that sha. With drafts, `submit --state approved --sha
<head_sha>` publishes and approves in one review instead of two, and refuses
unless both the PR head and the pending review sit on that sha.

**General note.** `note` posts a general PR comment. GitHub general comments
are never resolvable, so it never blocks a merge.

**Discarding.** `discard-drafts` deletes this run's comments from the pending
review and, when this run created that review and it is now empty, the review
itself. It fails on a ledger path that does not exist rather than reading it as
empty. It and a successful `submit` empty the ledger.

**A lost submit answer.** When `submit` dies on a 5xx after GitHub published
the review, the retry finds no pending review and stops, naming the threads the
drafts asked to resolve or reopen. Check `threads`, apply those by hand with
`resolve` / `unresolve`, then delete the ledger.

**Errors.** GitHub answers 5xx and secondary rate limits under load. On any
non-JSON response, run `drafts` or `threads` before retrying.

**Editing.** `edit --note <comment id>` replaces a review comment's body and
keeps its anchor. For a general comment, pass `--discussion issuecomment-<id>`
as well.

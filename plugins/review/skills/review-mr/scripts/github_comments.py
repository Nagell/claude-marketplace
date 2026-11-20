#!/usr/bin/env python3
"""Helpers for reviewing a GitHub pull request, mirroring gitlab_comments.py.

Same subcommands, flags and output shape as the GitLab script wherever GitHub
allows it, so the review flow in SKILL.md reads the same on both platforms.
``--project`` is ``owner/repo`` and ``--iid`` is the PR number. Calls go
through ``gh api`` (REST) and ``gh api graphql``; GitHub's review threads,
pending reviews and thread resolution exist only in GraphQL.

Differences from GitLab, also described in platforms/github.md:
  - A "discussion id" is a review thread's GraphQL node id (``PRRT_...``).
    General comments appear in ``threads`` as ``issuecomment-<id>`` and review
    summaries as ``review-<id>``; neither can be resolved.
  - Drafts are the comments of the viewer's one pending review. A draft with
    no line anchor (general, or ``--outside`` on a file the PR does not touch)
    has nowhere to live in a pending review, so the ledger keeps its text and
    ``submit`` puts it in the review body.
  - Publishing a reply never changes a thread's resolved state, so
    ``--resolve`` and ``--reopen`` are applied by ``submit`` after publishing.
  - ``submit --state approved`` publishes and approves in one review.

Subcommands:
  refs         print merge-base/base/head shas + changed paths for a PR
  counterpart  find the sibling repo's PR for the same change (same branch, or linked)
  diff         dump the PR diff to a file
  added-lines  list line numbers that are ADDED in the new file
  list         list existing comments (optionally filtered by author)
  threads      dump threads as JSON (ownership, resolved state, full bodies)
  post         post one inline comment right away
  edit         replace an existing comment's body, keeping its anchor
  reply        append a comment to an existing thread right away
  resolve      mark a thread resolved  (refuses threads we did not open)
  unresolve    reopen a thread         (refuses threads we did not open)
  note         post a general PR comment (never resolvable)
  approve      approve the PR, refused unless its head is still the given sha
  me           print the login gh is authenticated as

Review flow (one GitHub review, one notification, one verdict):
  drafts          list the comments of our pending review
  draft           add one comment to the pending review; recorded in a ledger file
  submit          submit the pending review with a body and an event
  discard-drafts  delete the drafts a ledger recorded that are still pending
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys

EVENTS = {
    "requested_changes": "REQUEST_CHANGES",
    "reviewed": "COMMENT",
    "approved": "APPROVE",
}
SEVERITY = re.compile(r"\*\*(Critical|Blocker|High|Medium|Low)\b")


def gh(path: str, repo_dir: str | None = None, method: str = "GET",
       body: dict | None = None) -> dict | list:
    """Call ``gh api`` and parse the JSON response.

    Exits with the raw output when the response is not JSON. A write may still
    have landed in that case, so callers must re-list before retrying.
    """
    cmd = ["gh", "api", "--method", method, path]
    stdin = None
    if body is not None:
        cmd += ["-H", "Content-Type: application/json", "--input", "-"]
        stdin = json.dumps(body)
    proc = subprocess.run(cmd, cwd=repo_dir, input=stdin, capture_output=True, text=True)
    if proc.returncode == 0 and not proc.stdout.strip():
        return {}
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        sys.exit(
            f"gh api {method} {path} did not return JSON.\n"
            f"stdout: {proc.stdout.strip()[:500]}\n"
            f"stderr: {proc.stderr.strip()[:500]}\n"
            "If this was a write, re-run `drafts` or `threads` before retrying "
            "so you do not double-post."
        )


def graphql(query: str, repo_dir: str | None = None, **variables) -> dict:
    """Run one GraphQL query or mutation; exit on any error GitHub reports."""
    proc = subprocess.run(
        ["gh", "api", "graphql", "--input", "-"], cwd=repo_dir,
        input=json.dumps({"query": query, "variables": variables}),
        capture_output=True, text=True,
    )
    try:
        out = json.loads(proc.stdout)
    except json.JSONDecodeError:
        sys.exit(f"gh api graphql did not return JSON.\nstdout: {proc.stdout[:500]}\n"
                 f"stderr: {proc.stderr[:500]}")
    if out.get("errors"):
        sys.exit(f"GraphQL error: {json.dumps(out['errors'])[:800]}")
    return out["data"]


def pr_base(a) -> str:
    return f"repos/{a.project}/pulls/{a.iid}"


def _pr(a) -> dict:
    pr = gh(pr_base(a), a.repo_dir)
    if "head" not in pr:
        sys.exit(f"no PR {a.project}#{a.iid}: {pr.get('message', pr)}")
    return pr


def _paged(path: str, repo_dir: str | None) -> list[dict]:
    """Every item of a REST list endpoint, across all pages."""
    per_page = 100
    sep = "&" if "?" in path else "?"
    out: list[dict] = []
    page = 1
    while True:
        batch = gh(f"{path}{sep}per_page={per_page}&page={page}", repo_dir)
        out += batch
        if len(batch) < per_page:
            return out
        page += 1


def merge_base(a, base: str, head: str) -> str:
    cmp = gh(f"repos/{a.project}/compare/{base}...{head}", a.repo_dir)
    return cmp["merge_base_commit"]["sha"]


def _refs(a) -> dict:
    """GitLab-shaped refs: base_sha is the merge base the PR diff is taken from."""
    pr = _pr(a)
    return {
        "base_sha": merge_base(a, pr["base"]["sha"], pr["head"]["sha"]),
        "start_sha": pr["base"]["sha"],
        "head_sha": pr["head"]["sha"],
        "pr": pr,
    }


def normalise_file(f: dict) -> dict:
    """One /files entry in the shape the GitLab script uses."""
    patch = f.get("patch")
    if patch is None and (f.get("additions", 0) + f.get("deletions", 0)) > 0:
        sys.exit(f"GitHub withheld the diff of {f['filename']} (too large); "
                 "anchor on it by hand or not at all")
    return {
        "new_path": f["filename"],
        "old_path": f.get("previous_filename") or f["filename"],
        "diff": patch or "",
    }


def _changes(a) -> list[dict]:
    return [normalise_file(f) for f in _paged(f"{pr_base(a)}/files", a.repo_dir)]


def cmd_refs(a) -> None:
    r = _refs(a)
    print(f"base_sha  {r['base_sha']}")
    print(f"start_sha {r['start_sha']}")
    print(f"head_sha  {r['head_sha']}")
    print(f"branch    {r['pr']['head']['ref']} -> {r['pr']['base']['ref']}")
    print("changed:")
    for c in _changes(a):
        print(f"  {c['new_path']}")


def cmd_diff(a) -> None:
    out = []
    for c in _changes(a):
        out.append(f"##### FILE: {c['new_path']}")
        out.append(c["diff"])
    text = "\n".join(out)
    with open(a.out, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(f"wrote {a.out} ({len(text.splitlines())} lines)")


def added_line_map(changes: list[dict]) -> dict[str, dict[int, str]]:
    """Map new-file line numbers to their content, for ADDED lines only."""
    result: dict[str, dict[int, str]] = {}
    for c in changes:
        n = None
        added: dict[int, str] = {}
        for line in c["diff"].splitlines():
            m = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)", line)
            if m:
                n = int(m.group(1))
                continue
            if n is None or line.startswith("-"):
                continue
            if line.startswith("+"):
                added[n] = line[1:]
            n += 1
        result[c["new_path"]] = added
    return result


def cmd_added_lines(a) -> None:
    for path, added in added_line_map(_changes(a)).items():
        if a.file and not path.endswith(a.file):
            continue
        print(f"== {path}")
        for line in sorted(added):
            print(f"  {line}: {added[line][:100]}")


def diff_rows(diff: str) -> dict[int, str]:
    """New-file lines a comment can anchor on (RIGHT side): added or context."""
    rows: dict[int, str] = {}
    new = None
    for line in diff.split("\n"):
        m = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)", line)
        if m:
            new = int(m.group(1))
            continue
        if new is None or not line or line.startswith("\\") or line.startswith("-"):
            continue
        rows[new] = "new" if line.startswith("+") else "context"
        new += 1
    return rows


def thread_input(change: dict, start: int, end: int) -> tuple[dict, str | None]:
    """addPullRequestReviewThread input for start..end, clamped to the diff.

    Returns the input and a note when the span was clamped. GitHub rejects a
    line outside the hunks, so a span that runs past them is cut to the part
    inside, the same as the GitLab script does.
    """
    rows = diff_rows(change["diff"])
    covered = [n for n in range(start, end + 1) if n in rows]
    path = change["new_path"]
    if not covered:
        sys.exit(f"{path}:{start}-{end} is outside the diff. Draft it with "
                 "--outside as a file-level comment in the same review.")
    note = None
    if (covered[0], covered[-1]) != (start, end):
        note = (f"  clamped {path}:{start}-{end} to {covered[0]}-{covered[-1]}, "
                "the rest is outside the diff")
    start, end = covered[0], covered[-1]
    inp = {"path": path, "line": end, "side": "RIGHT", "subjectType": "LINE"}
    if start != end:
        inp.update(startLine=start, startSide="RIGHT")
    return inp, note


def outside_body(ref: str, body: str) -> str:
    """Wrap a finding on lines no hunk touched; a suggestion fence becomes code."""
    path = ref.rsplit(":", 1)[0]
    lang = path.rsplit(".", 1)[-1] if "." in path.rsplit("/", 1)[-1] else ""
    body = re.sub(r"^(\s*)(`{3,}|~{3,})suggestion\S*", rf"\1\2{lang}", body, flags=re.M)
    return f"**Outside the diff - `{ref}`**\n\n{body}"


def severity(body: str) -> str | None:
    m = SEVERITY.search(body.splitlines()[0] if body else "")
    return m.group(1).lower() if m else None


def current_user(repo_dir: str | None) -> str:
    return gh("user", repo_dir)["login"]


def cmd_me(a) -> None:
    print(current_user(a.repo_dir))


THREADS_Q = """
query($owner: String!, $name: String!, $number: Int!, $after: String) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {
      reviewThreads(first: 50, after: $after) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id isResolved path line originalLine
          comments(first: 100) {
            nodes { databaseId author { login } body createdAt originalCommit { oid } }
          }
        }
      }
    }
  }
}"""


def _owner_name(a) -> tuple[str, str]:
    owner, _, name = a.project.partition("/")
    if not name:
        sys.exit(f"--project must be owner/repo, got {a.project}")
    return owner, name


def review_threads(a) -> list[dict]:
    owner, name = _owner_name(a)
    out: list[dict] = []
    after = None
    while True:
        d = graphql(THREADS_Q, a.repo_dir, owner=owner, name=name,
                    number=int(a.iid), after=after)
        page = d["repository"]["pullRequest"]["reviewThreads"]
        out += page["nodes"]
        if not page["pageInfo"]["hasNextPage"]:
            return out
        after = page["pageInfo"]["endCursor"]


def _login(node: dict | None) -> str:
    return (node or {}).get("login") or "ghost"


def thread_record(t: dict, me: str) -> dict:
    """One review thread in the GitLab script's discussion shape."""
    notes = t["comments"]["nodes"]
    first = notes[0]
    return {
        "discussion_id": t["id"],
        "opened_by": _login(first["author"]),
        "ours": _login(first["author"]) == me,
        "resolvable": True,
        "resolved": bool(t["isResolved"]),
        "severity": severity(first["body"]),
        "path": t["path"],
        "new_line": t.get("originalLine") or t.get("line"),
        "head_sha": (first.get("originalCommit") or {}).get("oid"),
        "last_note_by": _login(notes[-1]["author"]),
        "notes": [{"note_id": n["databaseId"], "author": _login(n["author"]),
                   "created_at": n["createdAt"], "body": n["body"]} for n in notes],
    }


def single_record(kind: str, c: dict, me: str, created_key: str) -> dict:
    """A general comment or review summary: one note, never resolvable."""
    author = _login(c.get("user"))
    return {
        "discussion_id": f"{kind}-{c['id']}",
        "opened_by": author,
        "ours": author == me,
        "resolvable": False,
        "resolved": False,
        "severity": severity(c.get("body") or ""),
        "path": None,
        "new_line": None,
        "head_sha": c.get("commit_id"),
        "last_note_by": author,
        "notes": [{"note_id": c["id"], "author": author,
                   "created_at": c.get(created_key), "body": c.get("body") or ""}],
    }


def all_threads(a, me: str) -> list[dict]:
    out = [thread_record(t, me) for t in review_threads(a) if t["comments"]["nodes"]]
    for c in _paged(f"repos/{a.project}/issues/{a.iid}/comments", a.repo_dir):
        out.append(single_record("issuecomment", c, me, "created_at"))
    for r in _paged(f"{pr_base(a)}/reviews", a.repo_dir):
        if (r.get("body") or "").strip() and r.get("state") != "PENDING":
            out.append(single_record("review", r, me, "submitted_at"))
    return out


def cmd_threads(a) -> None:
    me = current_user(a.repo_dir)
    out = [t for t in all_threads(a, me) if not a.mine or t["ours"]]
    text = json.dumps({"me": me, "discussions": out}, indent=2)
    if not a.out:
        print(text)
        return
    with open(a.out, "w", encoding="utf-8") as fh:
        fh.write(text)
    ours = [t for t in out if t["ours"]]
    print(f"wrote {a.out}: {len(out)} threads, {len(ours)} ours "
          f"({sum(1 for t in ours if t['resolved'])} of ours resolved)")


def cmd_list(a) -> None:
    for t in all_threads(a, current_user(a.repo_dir)):
        for n in t["notes"]:
            if a.author and n["author"] != a.author:
                continue
            anchor = f"{t['path']}:{t['new_line']}" if t["path"] else "UNANCHORED"
            state = "resolved" if t["resolved"] else "open"
            head = n["body"].splitlines()[0][:70] if n["body"] else ""
            print(f"{t['discussion_id']} {n['note_id']} {n['author']} [{state}] {anchor}")
            print(f"   {head}")


THREAD_Q = """
query($id: ID!) {
  node(id: $id) {
    ... on PullRequestReviewThread {
      id isResolved
      comments(first: 1) { nodes { databaseId author { login } } }
    }
  }
}"""


def _thread(a, tid: str) -> dict:
    if not tid.startswith("PRRT_"):
        sys.exit(f"{tid} is not a review thread id. Take the whole PRRT_... id from "
                 "`threads`; general comments and review summaries have no thread.")
    node = graphql(THREAD_Q, a.repo_dir, id=tid).get("node")
    if not node or not node.get("comments", {}).get("nodes"):
        sys.exit(f"no review thread {tid} on {a.project}#{a.iid}")
    return node


def _require_ours(a, tid: str) -> dict:
    """Refuse to change the state of a thread somebody else opened."""
    t = _thread(a, tid)
    owner = _login(t["comments"]["nodes"][0]["author"])
    me = current_user(a.repo_dir)
    if owner != me:
        sys.exit(f"refusing: thread {tid} was opened by {owner}, not {me}. Only the "
                 "author of a thread may resolve or reopen it - reply instead if you "
                 "want to say something on it.")
    return t


RESOLVE_M = {
    True: "mutation($id: ID!) { resolveReviewThread(input: {threadId: $id}) "
          "{ thread { isResolved } } }",
    False: "mutation($id: ID!) { unresolveReviewThread(input: {threadId: $id}) "
           "{ thread { isResolved } } }",
}


def set_resolved(a, tid: str, want: bool) -> None:
    _require_ours(a, tid)
    d = graphql(RESOLVE_M[want], a.repo_dir, id=tid)
    key = "resolveReviewThread" if want else "unresolveReviewThread"
    got = d[key]["thread"]["isResolved"]
    if got is not want:
        sys.exit(f"thread {tid} still reads resolved={got} after asking for {want} - "
                 "GitHub did not apply it, check the thread by hand.")
    print(f"  discussion={tid} resolved={got}")


def cmd_resolve(a) -> None:
    set_resolved(a, a.discussion, True)


def cmd_unresolve(a) -> None:
    set_resolved(a, a.discussion, False)


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def cmd_post(a) -> None:
    refs = _refs(a)
    if a.line not in added_line_map(_changes(a)).get(a.path, {}):
        sys.exit(f"{a.path}:{a.line} is not an added line in this PR. Run "
                 "`added-lines` and pick one.")
    c = gh(f"{pr_base(a)}/comments", a.repo_dir, "POST", {
        "body": _read(a.file), "commit_id": refs["head_sha"],
        "path": a.path, "line": a.line, "side": "RIGHT",
    })
    if (c.get("path"), c.get("line")) != (a.path, a.line):
        sys.exit(f"comment not anchored as asked: {c.get('message', c)}")
    print(f"  note={c['id']} anchored={c['path']}:{c['line']} ({len(c['body'])} chars)")


def cmd_edit(a) -> None:
    body = _read(a.file)
    if a.discussion and not a.discussion.startswith("PRRT_"):
        c = gh(f"repos/{a.project}/issues/comments/{a.note}", a.repo_dir, "PATCH",
               {"body": body})
        print(f"  note={c['id']} {len(c['body'])} chars (general comment)")
        return
    c = gh(f"repos/{a.project}/pulls/comments/{a.note}", a.repo_dir, "PATCH",
           {"body": body})
    if not c.get("path"):
        sys.exit(f"comment {a.note} not updated: {c.get('message', c)}")
    print(f"  note={c['id']} {len(c['body'])} chars, still anchored "
          f"{c['path']}:{c.get('line') or c.get('original_line')}")


def cmd_reply(a) -> None:
    first = _thread(a, a.discussion)["comments"]["nodes"][0]["databaseId"]
    c = gh(f"{pr_base(a)}/comments/{first}/replies", a.repo_dir, "POST",
           {"body": _read(a.file)})
    if "id" not in c:
        sys.exit(f"reply not created: {c.get('message', c)}")
    print(f"  replied note={c['id']} on discussion={a.discussion} ({len(c['body'])} chars)")


def cmd_note(a) -> None:
    """Post a general PR comment. GitHub general comments are never resolvable."""
    c = gh(f"repos/{a.project}/issues/{a.iid}/comments", a.repo_dir, "POST",
           {"body": _read(a.file)})
    if "id" not in c:
        sys.exit(f"note not created: {c.get('message', c)}")
    print(f"  note={c['id']} resolvable=False ({len(c['body'])} chars)")


def cmd_approve(a) -> None:
    """Approve at the sha we reviewed; GitHub itself would accept a stale sha."""
    head = _pr(a)["head"]["sha"]
    if head != a.sha:
        sys.exit(f"{a.project}#{a.iid} head is {head[:12]}, not {a.sha[:12]}: the "
                 "author pushed since the review - re-run `refs` and re-check first.")
    r = gh(f"{pr_base(a)}/reviews", a.repo_dir, "POST",
           {"commit_id": a.sha, "event": "APPROVE"})
    if r.get("state") != "APPROVED":
        sys.exit(f"{a.project}#{a.iid} not approved: {r.get('message', r)}")
    print(f"  #{a.iid} approved by {_login(r.get('user'))} at {a.sha[:12]}")


PENDING_Q = """
query($owner: String!, $name: String!, $number: Int!) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {
      id
      reviews(states: [PENDING], first: 5) {
        nodes {
          id databaseId body author { login } commit { oid }
          comments(first: 100) {
            nodes { id databaseId path line startLine body replyTo { databaseId } }
          }
        }
      }
    }
  }
}"""


def pending_review(a) -> tuple[str, dict | None]:
    """The PR node id and the viewer's pending review, if any.

    GitHub shows a pending review only to its author, and allows one per user.
    """
    owner, name = _owner_name(a)
    pr = graphql(PENDING_Q, a.repo_dir, owner=owner, name=name,
                 number=int(a.iid))["repository"]["pullRequest"]
    reviews = pr["reviews"]["nodes"]
    return pr["id"], (reviews[0] if reviews else None)


def _pending_comments(review: dict | None) -> list[dict]:
    return review["comments"]["nodes"] if review else []


def _ledger(path: str) -> list[dict]:
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return []


def _write_ledger(path: str, ledger: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(ledger, fh, indent=2)


def ledger_comment_ids(ledger: list[dict]) -> set[int]:
    return {e["id"] for e in ledger if e.get("kind") == "comment"}


def foreign_comments(review: dict | None, ledger: list[dict]) -> list[int]:
    ours = ledger_comment_ids(ledger)
    return [c["databaseId"] for c in _pending_comments(review) if c["databaseId"] not in ours]


def cmd_drafts(a) -> None:
    _, review = pending_review(a)
    comments = _pending_comments(review)
    for c in comments:
        where = f"{c['path']}:{c['line']}"
        if c.get("replyTo"):
            where = f"reply on comment {c['replyTo']['databaseId']}"
        head = c["body"].splitlines()[0][:70] if c["body"] else ""
        print(f"{c['databaseId']} {where}\n   {head}")
    if review and (review.get("body") or "").strip():
        print(f"pending review {review['databaseId']} also holds a body")
    print(f"{len(comments)} pending draft(s)")


ADD_REVIEW_M = """
mutation($pr: ID!, $sha: GitObjectID!) {
  addPullRequestReview(input: {pullRequestId: $pr, commitOID: $sha}) {
    pullRequestReview { id databaseId }
  }
}"""
ADD_THREAD_M = """
mutation($input: AddPullRequestReviewThreadInput!) {
  addPullRequestReviewThread(input: $input) {
    thread { id line path comments(first: 1) { nodes { id databaseId line } } }
  }
}"""
ADD_REPLY_M = """
mutation($input: AddPullRequestReviewThreadReplyInput!) {
  addPullRequestReviewThreadReply(input: $input) { comment { id databaseId } }
}"""
DELETE_COMMENT_M = """
mutation($id: ID!) { deletePullRequestReviewComment(input: {id: $id}) { clientMutationId } }"""
DELETE_REVIEW_M = """
mutation($id: ID!) { deletePullRequestReview(input: {pullRequestReviewId: $id}) {
  clientMutationId } }"""


def ensure_pending_review(a, ledger: list[dict]) -> str:
    """Node id of the pending review the drafts go in, creating it if needed."""
    pr_id, review = pending_review(a)
    foreign = foreign_comments(review, ledger)
    if foreign:
        sys.exit(f"refusing: you hold a pending review on {a.project}#{a.iid} with "
                 f"{len(foreign)} comment(s) not from this run ({foreign}). Submit or "
                 "discard it first - GitHub allows one pending review per user.")
    if review:
        return review["id"]
    head = _pr(a)["head"]["sha"]
    r = graphql(ADD_REVIEW_M, a.repo_dir, pr=pr_id, sha=head)
    created = r["addPullRequestReview"]["pullRequestReview"]
    ledger.append({"id": created["databaseId"], "node_id": created["id"],
                   "kind": "review", "label": "_review", "where": f"pending review at {head[:12]}"})
    return created["id"]


def _draft_reply(a, review_id: str, body: str) -> tuple[dict, str, dict]:
    if a.resolve and a.reopen:
        sys.exit("--resolve and --reopen contradict each other")
    thread = _require_ours(a, a.reply) if (a.resolve or a.reopen) else _thread(a, a.reply)
    d = graphql(ADD_REPLY_M, a.repo_dir, input={
        "pullRequestReviewId": review_id, "pullRequestReviewThreadId": thread["id"],
        "body": body})
    extra: dict = {}
    kind = f"reply on {a.reply}"
    if a.resolve:
        extra = {"resolve": a.reply, "resolve_after_submit": True}
        kind += " + resolve after submit"
    if a.reopen:
        extra = {"reopen": a.reply}
        kind += " + reopen after submit"
    return d["addPullRequestReviewThreadReply"]["comment"], kind, extra


def _draft_thread(a, review_id: str, inp: dict, kind: str) -> dict:
    inp = {**inp, "pullRequestReviewId": review_id}
    thread = graphql(ADD_THREAD_M, a.repo_dir, input=inp)["addPullRequestReviewThread"]["thread"]
    comment = thread["comments"]["nodes"][0]
    if inp["subjectType"] == "LINE" and not thread.get("line"):
        graphql(DELETE_COMMENT_M, a.repo_dir, id=comment["id"])
        sys.exit(f"draft for {kind} came back unanchored; deleted it")
    return comment


def _draft_location(a, body: str) -> tuple[dict | None, str, str]:
    """(thread input or None for the review body, kind, body to post)."""
    changes = {c["new_path"]: c for c in _changes(a)}
    if a.outside:
        path = a.outside.rsplit(":", 1)[0]
        wrapped = outside_body(a.outside, body)
        if path in changes:
            return ({"path": path, "subjectType": "FILE"},
                    f"outside the diff {a.outside} (file comment)", wrapped)
        return None, f"outside the diff {a.outside} (review body)", wrapped
    if a.path:
        if a.line is None:
            sys.exit("--path needs --line")
        if a.path not in changes:
            sys.exit(f"{a.path} is not a changed file in {a.project}#{a.iid}")
        end = a.end_line if a.end_line is not None else a.line
        start, end = min(a.line, end), max(a.line, end)
        inp, note = thread_input(changes[a.path], start, end)
        if note:
            print(note)
        return inp, f"{a.path}:{start}" + (f"-{end}" if end != start else ""), body
    return None, "general (review body)", body


def cmd_draft(a) -> None:
    """Add one draft to the pending review and record it in the ledger.

    The ledger is what lets a failed or interrupted run delete its own drafts,
    which the next run would otherwise mistake for a review the user started.
    """
    body = _read(a.file)
    ledger = _ledger(a.ledger)
    entry: dict = {"label": a.label}
    if a.reply:
        review_id = ensure_pending_review(a, ledger)
        comment, kind, extra = _draft_reply(a, review_id, body)
        entry.update(extra)
    else:
        inp, kind, body = _draft_location(a, body)
        if inp is None:
            entry.update(id=None, kind="body", where=kind, body=body)
            ledger.append(entry)
            _write_ledger(a.ledger, ledger)
            print(f"  draft {a.label} {kind}: kept in the ledger for the review body "
                  f"({len(body)} chars)")
            return
        inp["body"] = body
        review_id = ensure_pending_review(a, ledger)
        comment = _draft_thread(a, review_id, inp, kind)
    entry.update(id=comment["databaseId"], node_id=comment["id"], kind="comment", where=kind)
    ledger.append(entry)
    _write_ledger(a.ledger, ledger)
    print(f"  draft={comment['databaseId']} {a.label} {kind} ({len(body)} chars)")


def review_body(summary: str | None, ledger: list[dict]) -> str:
    """The summary note followed by every draft that had no anchor."""
    parts = [summary.strip()] if summary and summary.strip() else []
    parts += [e["body"].strip() for e in ledger if e.get("kind") == "body"]
    return "\n\n---\n\n".join(parts)


SUBMIT_M = """
mutation($id: ID!, $event: PullRequestReviewEvent!, $body: String) {
  submitPullRequestReview(input: {pullRequestReviewId: $id, event: $event, body: $body}) {
    pullRequestReview { databaseId state }
  }
}"""


def _check_submit(a, review: dict | None, ledger: list[dict], body: str) -> None:
    foreign = foreign_comments(review, ledger)
    if foreign:
        sys.exit(f"refusing: {len(foreign)} pending draft(s) on {a.project}#{a.iid} are "
                 f"not in this run's ledger ({foreign}). Submitting would publish them "
                 "too - the user has to submit or discard them first.")
    if a.state == "requested_changes" and not body:
        sys.exit("GitHub needs a review body to request changes: pass --file with "
                 "one line on what blocks.")
    if a.state == "approved":
        head = _pr(a)["head"]["sha"]
        at = (review or {}).get("commit", {}).get("oid") or head
        if at != head:
            sys.exit(f"the pending review sits on {at[:12]} but the head is {head[:12]}: "
                     "the author pushed since - re-check before approving.")


def _submit_without_drafts(a, body: str) -> dict:
    """No anchored draft: the review is only a body, created and submitted at once."""
    head = _pr(a)["head"]["sha"]
    r = gh(f"{pr_base(a)}/reviews", a.repo_dir, "POST",
           {"commit_id": head, "body": body, "event": EVENTS[a.state]})
    if "state" not in r:
        sys.exit(f"review not created: {r.get('message', r)}")
    return {"databaseId": r["id"], "state": r["state"]}


def cmd_submit(a) -> None:
    """Submit the pending review, then read back what landed."""
    ledger = _ledger(a.ledger)
    _, review = pending_review(a)
    body = review_body(_read(a.file) if a.file else None, ledger)
    _check_submit(a, review, ledger, body)
    ours = ledger_comment_ids(ledger)
    if review is None:
        if ours:
            sys.exit("no pending review found, but the ledger holds drafted comments. "
                     "Run `threads` - they may have published already.")
        result = _submit_without_drafts(a, body)
    else:
        result = graphql(SUBMIT_M, a.repo_dir, id=review["id"], event=EVENTS[a.state],
                         body=body or None)["submitPullRequestReview"]["pullRequestReview"]
    _, after = pending_review(a)
    left = [c["databaseId"] for c in _pending_comments(after) if c["databaseId"] in ours]
    print(f"  published {len(ours) - len(left)}/{len(ours)} drafts, "
          f"review state={result['state']} (asked {a.state})")
    if left:
        sys.exit(f"{len(left)} draft(s) still pending: {left}. Run `threads` before "
                 "anything else - some may have published anyway - then "
                 "`discard-drafts` the rest.")
    settle_thread_states(a, ledger)


def settle_thread_states(a, ledger: list[dict]) -> None:
    """Apply the resolves and reopens the drafts asked for, after publishing."""
    for entry in ledger:
        for key, want in (("resolve", True), ("reopen", False)):
            tid = entry.get(key)
            if not tid:
                continue
            if _thread(a, tid)["isResolved"] is want:
                print(f"  {entry['label']}: discussion={tid} resolved={want}")
                continue
            set_resolved(a, tid, want)


def cmd_discard_drafts(a) -> None:
    ledger = _ledger(a.ledger)
    ours = ledger_comment_ids(ledger)
    _, review = pending_review(a)
    gone = 0
    for c in _pending_comments(review):
        if c["databaseId"] in ours:
            graphql(DELETE_COMMENT_M, a.repo_dir, id=c["id"])
            gone += 1
    _, review = pending_review(a)
    created = {e["node_id"] for e in ledger if e.get("kind") == "review"}
    if review and review["id"] in created and not _pending_comments(review):
        graphql(DELETE_REVIEW_M, a.repo_dir, id=review["id"])
        print(f"  deleted the pending review this run created ({review['databaseId']})")
    still = sorted(ours & {c["databaseId"] for c in _pending_comments(pending_review(a)[1])})
    if still:
        sys.exit(f"drafts {still} survived the delete")
    print(f"  deleted {gone} draft(s) of this run; none of ours left pending")


def linked_numbers(description: str, sibling: str) -> list[str]:
    """PR numbers in the sibling repo that the description links or references."""
    repo = re.escape(sibling)
    found = re.findall(rf"github\.com/{repo}/pull/(\d+)", description)
    found += re.findall(rf"(?<![\w/.-]){repo}#(\d+)", description)
    return list(dict.fromkeys(found))


def cmd_counterpart(a) -> None:
    """Find the sibling repo's PR for the same change: same head branch, or linked."""
    pr = _pr(a)
    branch = pr["head"]["ref"]
    head_repo = pr["head"].get("repo") or {}
    owner = (head_repo.get("owner") or {}).get("login") or a.project.split("/")[0]
    found: dict[str, str] = {}
    same = gh(f"repos/{a.sibling}/pulls?state=open&per_page=100&head={owner}:{branch}",
              a.repo_dir)
    for m in same:
        found[str(m["number"])] = "same branch"
    for n in linked_numbers(pr.get("body") or "", a.sibling):
        found.setdefault(n, "linked in description")
    if not found:
        print(f"none: no open {a.sibling} PR on {branch}, none linked")
        return
    for n, how in found.items():
        c = gh(f"repos/{a.sibling}/pulls/{n}", a.repo_dir)
        sib = argparse.Namespace(project=a.sibling, repo_dir=a.repo_dir)
        base = merge_base(sib, c["base"]["sha"], c["head"]["sha"])
        print(f"#{n} ({how}) {c['state']}{' draft' if c.get('draft') else ''}")
        print(f"  url       {c['html_url']}")
        print(f"  branch    {c['head']['ref']} -> {c['base']['ref']}")
        print(f"  base_sha  {base}")
        print(f"  head_sha  {c['head']['sha']}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--project", required=True, help="owner/repo")
    p.add_argument("--iid", required=True, help="PR number")
    p.add_argument("--repo-dir", default=None, help="cwd for gh")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("refs").set_defaults(func=cmd_refs)
    cp = sub.add_parser("counterpart")
    cp.add_argument("--sibling", required=True, help="the other repo, owner/repo")
    cp.set_defaults(func=cmd_counterpart)
    d = sub.add_parser("diff")
    d.add_argument("--out", required=True)
    d.set_defaults(func=cmd_diff)
    al = sub.add_parser("added-lines")
    al.add_argument("--file", default=None, help="only paths ending with this")
    al.set_defaults(func=cmd_added_lines)
    ls = sub.add_parser("list")
    ls.add_argument("--author", default=None)
    ls.set_defaults(func=cmd_list)
    po = sub.add_parser("post")
    po.add_argument("--file", required=True)
    po.add_argument("--path", required=True)
    po.add_argument("--line", required=True, type=int)
    po.set_defaults(func=cmd_post)
    ed = sub.add_parser("edit")
    ed.add_argument("--file", required=True)
    ed.add_argument("--discussion", default=None,
                    help="thread id; an issuecomment-<id> edits a general comment")
    ed.add_argument("--note", required=True, help="comment id")
    ed.set_defaults(func=cmd_edit)
    sub.add_parser("me").set_defaults(func=cmd_me)
    th = sub.add_parser("threads")
    th.add_argument("--out", default=None)
    th.add_argument("--mine", action="store_true")
    th.set_defaults(func=cmd_threads)
    rp = sub.add_parser("reply")
    rp.add_argument("--file", required=True)
    rp.add_argument("--discussion", required=True)
    rp.set_defaults(func=cmd_reply)
    for name, func in (("resolve", cmd_resolve), ("unresolve", cmd_unresolve)):
        s = sub.add_parser(name)
        s.add_argument("--discussion", required=True)
        s.set_defaults(func=func)
    nt = sub.add_parser("note")
    nt.add_argument("--file", required=True)
    nt.set_defaults(func=cmd_note)
    ap = sub.add_parser("approve")
    ap.add_argument("--sha", required=True, help="head sha the review was done against")
    ap.set_defaults(func=cmd_approve)
    sub.add_parser("drafts").set_defaults(func=cmd_drafts)
    dr = sub.add_parser("draft")
    dr.add_argument("--file", required=True)
    dr.add_argument("--label", required=True, help="finding id, e.g. H1 or T2")
    dr.add_argument("--ledger", required=True)
    where = dr.add_mutually_exclusive_group()
    where.add_argument("--path")
    where.add_argument("--outside", metavar="PATH:LINES")
    where.add_argument("--reply", metavar="THREAD")
    dr.add_argument("--line", type=int)
    dr.add_argument("--end-line", type=int)
    dr.add_argument("--resolve", action="store_true",
                    help="with --reply: resolve the thread after submit (ours only)")
    dr.add_argument("--reopen", action="store_true",
                    help="with --reply: reopen the thread after submit (ours only)")
    dr.set_defaults(func=cmd_draft)
    sb = sub.add_parser("submit")
    sb.add_argument("--ledger", required=True)
    sb.add_argument("--state", required=True, choices=sorted(EVENTS))
    sb.add_argument("--file", default=None)
    sb.set_defaults(func=cmd_submit)
    dd = sub.add_parser("discard-drafts")
    dd.add_argument("--ledger", required=True)
    dd.set_defaults(func=cmd_discard_drafts)
    return p


def main() -> None:
    a = build_parser().parse_args()
    a.func(a)


if __name__ == "__main__":
    main()

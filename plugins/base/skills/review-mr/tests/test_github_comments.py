"""github_comments.py payload building and safety checks, with the network mocked.

``gh`` and ``graphql`` are replaced by a fake that answers from a small
in-memory PR and records every call, so the tests assert on what would have
been sent to GitHub.
"""

import argparse
import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import github_comments as g  # noqa: E402

HEAD = "h" * 40
BASE = "b" * 40
PATCH = "@@ -10,3 +10,5 @@ def f():\n ctx10\n+add11\n+add12\n ctx13\n-old\n+add14\n"


class FakeGitHub:
    def __init__(self, me="me", pending=None, thread_owner="me", thread_resolved=False):
        self.me = me
        self.author = "author"
        self.thread_pr = ("o/r", 7)
        self.files = [{"filename": "src/a.py", "patch": PATCH, "additions": 4, "deletions": 1}]
        self.pending = pending
        self.thread_owner = thread_owner
        self.thread_resolved = thread_resolved
        self.rest: list[tuple] = []
        self.gql: list[tuple] = []

    def gh(self, path, repo_dir=None, method="GET", body=None):
        self.rest.append((method, path, body))
        if path == "user":
            return {"login": self.me}
        if path.startswith("repos/o/r/pulls/7/files"):
            return self.files
        if path == "repos/o/r/pulls/7" and method == "GET":
            return {"head": {"sha": HEAD, "ref": "feat"}, "base": {"sha": BASE, "ref": "main"},
                    "node_id": "PR_1", "body": "", "user": {"login": self.author}}
        if path == "repos/o/r/pulls/7/reviews" and method == "POST":
            return {"id": 99, "state": body["event"].replace("APPROVE", "APPROVED")
                    .replace("COMMENT", "COMMENTED"), "user": {"login": self.me}}
        raise AssertionError(f"unexpected REST call {method} {path}")

    def graphql(self, query, repo_dir=None, **v):
        names = re.findall(r"(\w+)\(", query)
        if names[0] == "mutation":
            op = names[1]
        else:
            op = "pending" if "states: [PENDING]" in query else "node"
        self.gql.append((op, v))
        handler = getattr(self, f"op_{op}", None)
        if handler is None:
            raise AssertionError(f"unexpected GraphQL {op}")
        return handler(v)

    def op_pending(self, v):
        return {"repository": {"pullRequest": {
            "id": "PR_1", "reviews": {"nodes": [self.pending] if self.pending else []}}}}

    def op_addPullRequestReview(self, v):
        self.pending = {"id": "PRR_new", "databaseId": 500, "body": "",
                        "commit": {"oid": v["sha"]}, "comments": {"nodes": []}}
        return {"addPullRequestReview": {"pullRequestReview": {"id": "PRR_new",
                                                               "databaseId": 500}}}

    def op_addPullRequestReviewThread(self, v):
        line = v["input"].get("line")
        c = {"id": "C_1", "databaseId": 601, "line": line}
        self.pending["comments"]["nodes"].append(
            {"id": "C_1", "databaseId": 601, "path": v["input"]["path"], "line": line,
             "startLine": None, "body": v["input"]["body"], "replyTo": None})
        return {"addPullRequestReviewThread": {"thread": {
            "id": "PRRT_new", "line": line, "path": v["input"]["path"],
            "comments": {"nodes": [c]}}}}

    def op_addPullRequestReviewThreadReply(self, v):
        self.pending["comments"]["nodes"].append(
            {"id": "C_2", "databaseId": 602, "path": "src/a.py", "line": None,
             "startLine": None, "body": v["input"]["body"], "replyTo": {"databaseId": 1}})
        return {"addPullRequestReviewThreadReply": {"comment": {"id": "C_2",
                                                                "databaseId": 602}}}

    def op_node(self, v):
        repo, number = self.thread_pr
        return {"node": {"id": v["id"], "isResolved": self.thread_resolved,
                         "pullRequest": {"number": number,
                                         "repository": {"nameWithOwner": repo}},
                         "comments": {"nodes": [{"databaseId": 1,
                                                 "author": {"login": self.thread_owner}}]}}}

    def op_submitPullRequestReview(self, v):
        submitted, self.pending = self.pending, None
        state = {"REQUEST_CHANGES": "CHANGES_REQUESTED", "COMMENT": "COMMENTED",
                 "APPROVE": "APPROVED"}[v["event"]]
        return {"submitPullRequestReview": {"pullRequestReview": {
            "databaseId": submitted["databaseId"], "state": state}}}

    def op_resolveReviewThread(self, v):
        self.thread_resolved = True
        return {"resolveReviewThread": {"thread": {"isResolved": True}}}

    def op_unresolveReviewThread(self, v):
        self.thread_resolved = False
        return {"unresolveReviewThread": {"thread": {"isResolved": False}}}

    def op_deletePullRequestReviewComment(self, v):
        nodes = self.pending["comments"]["nodes"]
        self.pending["comments"]["nodes"] = [c for c in nodes if c["id"] != v["id"]]
        return {}

    def op_deletePullRequestReview(self, v):
        self.pending = None
        return {}

    def mutations(self, name):
        return [v for op, v in self.gql if op == name]


@pytest.fixture
def fake(monkeypatch):
    f = FakeGitHub()
    monkeypatch.setattr(g, "gh", f.gh)
    monkeypatch.setattr(g, "graphql", f.graphql)
    return f


def args(tmp_path, **kw):
    body = tmp_path / "body.md"
    body.write_text(kw.pop("text", "🟠 **High** - it breaks\n\nbecause."), encoding="utf-8")
    base = dict(project="o/r", iid="7", repo_dir=None, file=str(body), label="H1",
                ledger=str(tmp_path / "drafts.json"), path=None, line=None, end_line=None,
                outside=None, reply=None, resolve=False, reopen=False)
    base.update(kw)
    return argparse.Namespace(**base)


def ledger(tmp_path):
    return json.loads((tmp_path / "drafts.json").read_text())


# Pure helpers


def test_normalise_file_rename_and_binary():
    f = g.normalise_file({"filename": "new.py", "previous_filename": "old.py",
                          "patch": PATCH, "additions": 1, "deletions": 0})
    assert (f["new_path"], f["old_path"]) == ("new.py", "old.py")
    binary = g.normalise_file({"filename": "a.png", "additions": 0, "deletions": 0})
    assert binary["diff"] == ""


def test_normalise_file_withheld_diff_is_flagged_not_fatal():
    f = g.normalise_file({"filename": "big.json", "additions": 9000, "deletions": 0})
    assert f["withheld"] is True and f["diff"] == ""
    with pytest.raises(SystemExit, match="--outside"):
        g.thread_input(f, 1, 1)


def test_withheld_file_does_not_block_the_rest(fake, tmp_path):
    fake.files.append({"filename": "pnpm-lock.yaml", "additions": 9000, "deletions": 0})
    g.cmd_draft(args(tmp_path, path="src/a.py", line=11))
    assert len(fake.mutations("addPullRequestReviewThread")) == 1


def test_added_line_map_skips_no_newline_marker():
    patch = "@@ -1,2 +1,3 @@\n a\n-b\n\\ No newline at end of file\n+b\n+c\n"
    assert g.added_line_map([{"new_path": "x", "diff": patch}]) == {"x": {2: "b", 3: "c"}}


def test_diff_rows_skip_removed_lines():
    assert g.diff_rows(PATCH) == {10: "context", 11: "new", 12: "new", 13: "context", 14: "new"}


def test_thread_input_single_line():
    inp, note = g.thread_input({"new_path": "src/a.py", "diff": PATCH}, 11, 11)
    assert inp == {"path": "src/a.py", "line": 11, "side": "RIGHT", "subjectType": "LINE"}
    assert note is None


def test_thread_input_range_and_clamp():
    inp, note = g.thread_input({"new_path": "src/a.py", "diff": PATCH}, 8, 12)
    assert inp == {"path": "src/a.py", "line": 12, "side": "RIGHT", "subjectType": "LINE",
                   "startLine": 10, "startSide": "RIGHT"}
    assert "clamped src/a.py:8-12 to 10-12" in note


def test_thread_input_across_two_hunks_is_refused():
    two = PATCH + "@@ -30,2 +32,3 @@\n ctx32\n+add33\n ctx34\n"
    with pytest.raises(SystemExit, match="spans two hunks"):
        g.thread_input({"new_path": "src/a.py", "diff": two}, 12, 33)


def test_clamped_span_with_suggestion_is_refused(fake, tmp_path):
    text = "🟡 **Medium** - x\n\n```suggestion\na\nb\nc\nd\ne\n```\n"
    with pytest.raises(SystemExit, match="suggestion fence"):
        g.cmd_draft(args(tmp_path, path="src/a.py", line=8, end_line=12, text=text))
    assert not fake.mutations("addPullRequestReviewThread")


def test_thread_input_outside_the_diff_exits():
    with pytest.raises(SystemExit, match="--outside"):
        g.thread_input({"new_path": "src/a.py", "diff": PATCH}, 40, 47)


def test_outside_body_turns_suggestion_into_code():
    out = g.outside_body("src/a.py:40-47", "text\n```suggestion\nx = 1\n```\n")
    assert out.startswith("**Outside the diff - `src/a.py:40-47`**")
    assert "```py\nx = 1" in out and "suggestion" not in out


def test_review_body_joins_summary_and_unanchored_drafts():
    led = [{"kind": "comment", "id": 1}, {"kind": "body", "body": "general point\n"}]
    assert g.review_body("Blocks on H1.\n", led) == "Blocks on H1.\n\n---\n\ngeneral point"
    assert g.review_body(None, []) == ""


def test_linked_numbers():
    text = "See https://github.com/o/fe/pull/12 and o/fe#13, not xo/fe#14 or o/fe#12."
    assert g.linked_numbers(text, "o/fe") == ["12", "13"]


def test_thread_record_has_the_gitlab_shape():
    t = {"id": "PRRT_1", "isResolved": True, "path": "a.py", "line": None, "originalLine": 5,
         "comments": {"nodes": [
             {"databaseId": 1, "author": {"login": "me"}, "body": "🟡 **Medium** - x",
              "createdAt": "t1", "originalCommit": {"oid": "abc"}},
             {"databaseId": 2, "author": None, "body": "fixed", "createdAt": "t2",
              "originalCommit": {"oid": "def"}}]}}
    r = g.thread_record(t, "me")
    assert set(r) == {"discussion_id", "opened_by", "ours", "resolvable", "resolved",
                      "severity", "path", "new_line", "head_sha", "last_note_by", "notes"}
    assert (r["ours"], r["severity"], r["new_line"], r["head_sha"], r["last_note_by"]) == \
        (True, "medium", 5, "abc", "ghost")


# Draft flow


def test_draft_inline_range_creates_review_then_thread(fake, tmp_path):
    g.cmd_draft(args(tmp_path, path="src/a.py", line=12, end_line=10))
    (review,) = fake.mutations("addPullRequestReview")
    assert review == {"pr": "PR_1", "sha": HEAD}
    (thread,) = fake.mutations("addPullRequestReviewThread")
    assert thread["input"] == {"path": "src/a.py", "line": 12, "side": "RIGHT",
                               "subjectType": "LINE", "startLine": 10, "startSide": "RIGHT",
                               "body": "🟠 **High** - it breaks\n\nbecause.",
                               "pullRequestReviewId": "PRR_new"}
    kinds = [(e["kind"], e["id"]) for e in ledger(tmp_path)]
    assert kinds == [("review", 500), ("comment", 601)]


def test_draft_reuses_our_pending_review(fake, tmp_path):
    g.cmd_draft(args(tmp_path, path="src/a.py", line=11))
    g.cmd_draft(args(tmp_path, path="src/a.py", line=14, label="M1"))
    assert len(fake.mutations("addPullRequestReview")) == 1
    assert len(fake.mutations("addPullRequestReviewThread")) == 2


def test_draft_refuses_a_pending_review_the_user_started(fake, tmp_path):
    fake.pending = {"id": "PRR_user", "databaseId": 1, "body": "", "commit": {"oid": HEAD},
                    "comments": {"nodes": [{"id": "C_u", "databaseId": 77, "path": "x",
                                            "line": 1, "body": "mine", "replyTo": None}]}}
    with pytest.raises(SystemExit, match="not from this run"):
        g.cmd_draft(args(tmp_path, path="src/a.py", line=11))
    assert not fake.mutations("addPullRequestReviewThread")


def test_draft_outside_on_changed_file_is_a_file_comment(fake, tmp_path):
    g.cmd_draft(args(tmp_path, outside="src/a.py:40-47"))
    (thread,) = fake.mutations("addPullRequestReviewThread")
    assert thread["input"]["subjectType"] == "FILE"
    assert thread["input"]["body"].startswith("**Outside the diff - `src/a.py:40-47`**")


def test_draft_outside_on_untouched_file_goes_to_review_body(fake, tmp_path):
    g.cmd_draft(args(tmp_path, outside="src/other.py:3-4"))
    assert not fake.mutations("addPullRequestReview")
    (entry,) = ledger(tmp_path)
    assert entry["kind"] == "body" and entry["id"] is None
    assert entry["body"].startswith("**Outside the diff - `src/other.py:3-4`**")


def test_draft_resolve_refused_on_someone_elses_thread(fake, tmp_path):
    fake.thread_owner = "colleague"
    with pytest.raises(SystemExit, match="opened by colleague"):
        g.cmd_draft(args(tmp_path, reply="PRRT_x", resolve=True))
    assert not fake.mutations("addPullRequestReviewThreadReply")
    assert not fake.mutations("addPullRequestReview")


def test_thread_from_another_pr_is_refused(fake, tmp_path):
    fake.thread_pr = ("o/fe", 12)
    with pytest.raises(SystemExit, match="belongs to o/fe#12"):
        g.cmd_resolve(args(tmp_path, discussion="PRRT_x"))
    assert not fake.mutations("resolveReviewThread")


def test_draft_refuses_a_pending_review_holding_only_a_body(fake, tmp_path):
    fake.pending = {"id": "PRR_user", "databaseId": 1, "body": "my summary",
                    "commit": {"oid": HEAD}, "comments": {"nodes": []}}
    with pytest.raises(SystemExit, match="review body"):
        g.cmd_draft(args(tmp_path, path="src/a.py", line=11))


def test_draft_reply_with_resolve_is_recorded_for_submit(fake, tmp_path):
    g.cmd_draft(args(tmp_path, reply="PRRT_x", resolve=True, label="T1", text="✅ Verified"))
    (reply,) = fake.mutations("addPullRequestReviewThreadReply")
    assert reply["input"] == {"pullRequestReviewId": "PRR_new",
                              "pullRequestReviewThreadId": "PRRT_x", "body": "✅ Verified"}
    entry = ledger(tmp_path)[-1]
    assert entry["resolve"] == "PRRT_x" and entry["resolve_after_submit"] is True


def test_draft_resolve_and_reopen_contradict(fake, tmp_path):
    with pytest.raises(SystemExit, match="contradict"):
        g.cmd_draft(args(tmp_path, reply="PRRT_x", resolve=True, reopen=True))


def test_resolve_refuses_a_non_thread_id(fake, tmp_path):
    a = args(tmp_path, discussion="issuecomment-5")
    with pytest.raises(SystemExit, match="not a review thread"):
        g.cmd_resolve(a)


# Submit, approve, discard


def submit_args(tmp_path, state, summary=None):
    a = args(tmp_path, state=state)
    if summary is None:
        a.file = None
    else:
        (tmp_path / "summary.md").write_text(summary, encoding="utf-8")
        a.file = str(tmp_path / "summary.md")
    return a


def test_submit_maps_state_and_settles_resolves(fake, tmp_path):
    g.cmd_draft(args(tmp_path, path="src/a.py", line=11))
    g.cmd_draft(args(tmp_path, outside="src/other.py:3-4", label="M2", text="general"))
    g.cmd_draft(args(tmp_path, reply="PRRT_x", resolve=True, label="T1", text="✅ Verified"))
    g.cmd_submit(submit_args(tmp_path, "requested_changes", "Blocks on H1."))
    (sub,) = fake.mutations("submitPullRequestReview")
    assert sub["event"] == "REQUEST_CHANGES" and sub["id"] == "PRR_new"
    assert sub["body"].startswith("Blocks on H1.\n\n---\n\n**Outside the diff")
    assert len(fake.mutations("resolveReviewThread")) == 1
    assert fake.thread_resolved is True
    assert ledger(tmp_path) == []


def test_submit_refuses_foreign_drafts(fake, tmp_path):
    fake.pending = {"id": "PRR_user", "databaseId": 1, "body": "", "commit": {"oid": HEAD},
                    "comments": {"nodes": [{"id": "C_u", "databaseId": 77, "path": "x",
                                            "line": 1, "body": "mine", "replyTo": None}]}}
    with pytest.raises(SystemExit, match="not in this run's ledger"):
        g.cmd_submit(submit_args(tmp_path, "reviewed"))
    assert not fake.mutations("submitPullRequestReview")


def test_submit_request_changes_needs_a_body(fake, tmp_path):
    g.cmd_draft(args(tmp_path, path="src/a.py", line=11))
    with pytest.raises(SystemExit, match="needs a review body"):
        g.cmd_submit(submit_args(tmp_path, "requested_changes"))


def test_submit_approved_refused_when_head_moved(fake, tmp_path):
    g.cmd_draft(args(tmp_path, path="src/a.py", line=11))
    fake.pending["commit"]["oid"] = "0" * 40
    a = submit_args(tmp_path, "approved")
    a.sha = HEAD
    with pytest.raises(SystemExit, match="pushed since"):
        g.cmd_submit(a)


def test_submit_approved_checks_the_reviewed_sha_without_drafts(fake, tmp_path):
    a = submit_args(tmp_path, "approved")
    a.sha = "0" * 40
    with pytest.raises(SystemExit, match="pushed since"):
        g.cmd_submit(a)
    a.sha = None
    with pytest.raises(SystemExit, match="needs --sha"):
        g.cmd_submit(a)
    assert not [c for c in fake.rest if c[0] == "POST"]


def test_submit_on_own_pr_refuses_a_verdict(fake, tmp_path):
    fake.author = "me"
    g.cmd_draft(args(tmp_path, path="src/a.py", line=11))
    with pytest.raises(SystemExit, match="own PR"):
        g.cmd_submit(submit_args(tmp_path, "requested_changes", "Blocks."))
    assert not fake.mutations("submitPullRequestReview")


def test_submit_with_only_body_drafts_creates_a_review(fake, tmp_path):
    g.cmd_draft(args(tmp_path, label="G1", text="general point"))
    g.cmd_submit(submit_args(tmp_path, "reviewed"))
    posts = [c for c in fake.rest if c[0] == "POST"]
    assert posts == [("POST", "repos/o/r/pulls/7/reviews",
                      {"commit_id": HEAD, "body": "general point", "event": "COMMENT"})]


def test_approve_refused_when_head_moved(fake, tmp_path):
    with pytest.raises(SystemExit, match="pushed since"):
        g.cmd_approve(args(tmp_path, sha="0" * 40))
    assert not [c for c in fake.rest if c[0] == "POST"]


def test_approve_sends_the_reviewed_sha(fake, tmp_path):
    g.cmd_approve(args(tmp_path, sha=HEAD))
    post = next(c for c in fake.rest if c[0] == "POST")
    assert post[2] == {"commit_id": HEAD, "event": "APPROVE"}


def test_discard_deletes_only_ours_and_the_review_we_created(fake, tmp_path):
    g.cmd_draft(args(tmp_path, path="src/a.py", line=11))
    g.cmd_discard_drafts(args(tmp_path))
    assert [v["id"] for v in fake.mutations("deletePullRequestReviewComment")] == ["C_1"]
    assert [v["id"] for v in fake.mutations("deletePullRequestReview")] == ["PRR_new"]
    assert fake.pending is None
    assert ledger(tmp_path) == []


def test_discard_fails_on_a_missing_ledger(fake, tmp_path):
    with pytest.raises(SystemExit, match="no ledger"):
        g.cmd_discard_drafts(args(tmp_path, ledger=str(tmp_path / "typo.json")))


# Author-side commands (resolve-review)


def test_resolve_as_author_closes_a_reviewers_thread_on_our_pr(fake, tmp_path):
    fake.thread_owner, fake.author = "reviewer", "me"
    g.cmd_resolve(args(tmp_path, discussion="PRRT_1", as_author=True))
    assert fake.mutations("resolveReviewThread") == [{"id": "PRRT_1"}]


def test_resolve_as_author_refused_on_someone_elses_pr(fake, tmp_path):
    fake.thread_owner = "reviewer"
    with pytest.raises(SystemExit, match="opened by author"):
        g.cmd_resolve(args(tmp_path, discussion="PRRT_1", as_author=True))
    assert not fake.mutations("resolveReviewThread")


def test_resolve_without_as_author_still_refuses_a_reviewers_thread(fake, tmp_path):
    fake.thread_owner, fake.author = "reviewer", "me"
    with pytest.raises(SystemExit, match="opened by reviewer"):
        g.cmd_resolve(args(tmp_path, discussion="PRRT_1", as_author=False))
    assert not fake.mutations("resolveReviewThread")


def test_resolve_as_author_still_checks_the_thread_belongs_to_the_pr(fake, tmp_path):
    fake.thread_owner, fake.author = "reviewer", "me"
    fake.thread_pr = ("o/other", 3)
    with pytest.raises(SystemExit, match="belongs to o/other#3"):
        g.cmd_resolve(args(tmp_path, discussion="PRRT_1", as_author=True))


def test_threads_unresolved_keeps_only_open_review_threads(monkeypatch, fake, tmp_path,
                                                           capsys):
    rows = [
        {"discussion_id": "PRRT_open", "resolvable": True, "resolved": False, "ours": False},
        {"discussion_id": "PRRT_done", "resolvable": True, "resolved": True, "ours": False},
        {"discussion_id": "issuecomment-1", "resolvable": False, "resolved": False,
         "ours": False},
    ]
    monkeypatch.setattr(g, "all_threads", lambda a, me: rows)
    g.cmd_threads(args(tmp_path, out=None, mine=False, unresolved=True))
    got = json.loads(capsys.readouterr().out)["discussions"]
    assert [t["discussion_id"] for t in got] == ["PRRT_open"]


def test_for_branch_lists_open_prs_first(monkeypatch, fake, tmp_path, capsys):
    prs = [
        {"number": 3, "state": "closed", "merged_at": "x", "user": {"login": "me"},
         "title": "old", "html_url": "u3", "head": {"ref": "feat"}, "base": {"ref": "main"}},
        {"number": 5, "state": "open", "user": {"login": "me"}, "draft": True,
         "title": "new", "html_url": "u5", "head": {"ref": "feat"}, "base": {"ref": "main"}},
    ]
    monkeypatch.setattr(g, "_paged", lambda path, repo_dir: prs
                        if path == "repos/o/r/pulls?state=all&head=o:feat" else [])
    g.cmd_for_branch(args(tmp_path, iid=None, branch="feat"))
    lines = [ln for ln in capsys.readouterr().out.splitlines() if ln.startswith("#")]
    assert lines == ["#5 open draft by me: new", "#3 merged by me: old"]


def test_for_branch_says_none(monkeypatch, fake, tmp_path, capsys):
    monkeypatch.setattr(g, "_paged", lambda path, repo_dir: [])
    g.cmd_for_branch(args(tmp_path, iid=None, branch="feat"))
    assert capsys.readouterr().out.startswith("none: no PR on feat")


def test_iid_is_required_except_for_for_branch(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["github_comments.py", "--project", "o/r", "threads"])
    with pytest.raises(SystemExit):
        g.main()

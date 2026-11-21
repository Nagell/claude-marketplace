"""gitlab_comments.py safety checks, with ``glab`` replaced by an in-memory fake.

The fake answers from a small MR and records every call, so the tests assert
on what would have been sent to GitLab.
"""

import argparse
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import gitlab_comments as gl  # noqa: E402

MR = "projects/9/merge_requests/3"
DIFF = "@@ -10,3 +10,5 @@ def f():\n ctx10\n+add11\n+add12\n ctx13\n-old\n+add14\n"


class FakeGitLab:
    def __init__(self):
        self.me = "me"
        self.thread_owner = "me"
        self.thread_resolved = False
        self.drafts: list[dict] = []
        self.diffs = [{"new_path": "src/a.py", "old_path": "src/a.py", "diff": DIFF}]
        self.publish_answer: dict = {}
        self.notes: list[dict] = []
        self.calls: list[tuple] = []

    def glab(self, path, repo_dir=None, method="GET", body=None):
        self.calls.append((method, path, body))
        if path == "user":
            return {"username": self.me}
        if path.startswith(f"{MR}/diffs"):
            return self.diffs
        if path == MR:
            return {"diff_refs": {"base_sha": "b", "start_sha": "s", "head_sha": "h"}}
        if path.startswith(f"{MR}/discussions/") and method == "GET":
            return {"id": path.rsplit("/", 1)[1], "notes": [
                {"id": 1, "author": {"username": self.thread_owner},
                 "resolved": self.thread_resolved, "body": "x"}]}
        if path.startswith(f"{MR}/draft_notes/bulk_publish"):
            if not self.publish_answer:
                self.drafts = []
            return self.publish_answer
        if path.startswith(f"{MR}/draft_notes") and method == "GET":
            # Like GitLab: draft_notes ignores paging and returns every draft.
            return list(self.drafts)
        if path == f"{MR}/draft_notes" and method == "POST":
            d = {"id": 100 + len(self.drafts), "note": body["note"],
                 "position": body.get("position")}
            self.drafts.append(d)
            return d
        if path.startswith(f"{MR}/draft_notes/") and method == "DELETE":
            did = int(path.rsplit("/", 1)[1])
            self.drafts = [d for d in self.drafts if d["id"] != did]
            return {}
        if path.startswith(f"{MR}/reviewers"):
            return [{"user": {"username": self.me}, "state": "reviewed"}]
        if path.startswith(f"{MR}/notes") and method == "GET":
            return self.notes
        if "/notes/" in path and method == "PUT":
            return {"id": 5, "body": body["body"], "type": None, "position": None}
        raise AssertionError(f"unexpected glab call {method} {path}")

    def sent(self, method, prefix):
        return [b for m, p, b in self.calls if m == method and p.startswith(prefix)]


@pytest.fixture
def fake(monkeypatch):
    f = FakeGitLab()
    monkeypatch.setattr(gl, "glab", f.glab)
    return f


def args(tmp_path, **kw):
    body = tmp_path / "body.md"
    body.write_text(kw.pop("text", "🟠 **High** - it breaks"), encoding="utf-8")
    base = dict(project="9", iid="3", repo_dir=None, file=str(body), label="H1",
                ledger=str(tmp_path / "drafts.json"), path=None, line=None, end_line=None,
                outside=None, reply=None, resolve=False, reopen=False, state="reviewed",
                discussion=None, note=None)
    base.update(kw)
    return argparse.Namespace(**base)


def ledger(tmp_path):
    return json.loads((tmp_path / "drafts.json").read_text())


def test_reopen_refused_on_someone_elses_thread(fake, tmp_path):
    fake.thread_owner = "colleague"
    fake.thread_resolved = True
    with pytest.raises(SystemExit, match="opened by colleague"):
        gl.cmd_draft(args(tmp_path, reply="abc", reopen=True))
    assert not fake.sent("POST", f"{MR}/draft_notes")


def test_drafts_stop_when_gitlab_repeats_the_page(fake, tmp_path):
    fake.drafts = [{"id": i} for i in range(150)]
    assert len(gl._drafts(args(tmp_path))) == 150


def test_submit_exits_on_an_error_answer(fake, tmp_path):
    gl.cmd_draft(args(tmp_path, path="src/a.py", line=11))
    fake.publish_answer = {"message": "500 Internal Server Error"}
    with pytest.raises(SystemExit, match="bulk_publish answered"):
        gl.cmd_submit(args(tmp_path, state="requested_changes"))
    assert ledger(tmp_path) != []


def test_submit_reads_the_summary_back_and_clears_the_ledger(fake, tmp_path, capsys):
    gl.cmd_draft(args(tmp_path, path="src/a.py", line=11))
    (tmp_path / "summary.md").write_text("Blocks on H1.", encoding="utf-8")
    gl.cmd_submit(args(tmp_path, file=str(tmp_path / "summary.md")))
    assert "does not show on the MR" in capsys.readouterr().out
    assert ledger(tmp_path) == []


def test_edit_on_a_general_note_succeeds(fake, tmp_path, capsys):
    gl.cmd_edit(args(tmp_path, discussion="abc", note="5"))
    assert "general note" in capsys.readouterr().out


def test_withheld_file_is_flagged_and_only_its_anchor_refused(fake, tmp_path):
    fake.diffs.append({"new_path": "pnpm-lock.yaml", "old_path": "pnpm-lock.yaml",
                       "diff": "", "too_large": True})
    gl.cmd_draft(args(tmp_path, path="src/a.py", line=11))
    with pytest.raises(SystemExit, match="--outside"):
        gl.cmd_draft(args(tmp_path, path="pnpm-lock.yaml", line=1))


def test_clamped_span_with_suggestion_is_refused(fake, tmp_path):
    text = "🟡 **Medium** - x\n\n```suggestion:-4+0\na\nb\nc\nd\ne\n```\n"
    with pytest.raises(SystemExit, match="suggestion fence"):
        gl.cmd_draft(args(tmp_path, path="src/a.py", line=8, end_line=12, text=text))


def test_discard_fails_on_a_missing_ledger(fake, tmp_path):
    with pytest.raises(SystemExit, match="no ledger"):
        gl.cmd_discard_drafts(args(tmp_path, ledger=str(tmp_path / "typo.json")))

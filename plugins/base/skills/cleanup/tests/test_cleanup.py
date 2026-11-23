"""Run from the skill folder: python3 -m unittest discover -s tests

Every repo, remote, scratch root and session record here is a synthetic
fixture in a temporary folder. Nothing touches real user data.
"""

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import uuid
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "scripts", "cleanup.py")
spec = importlib.util.spec_from_file_location("cleanup", SCRIPT)
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)

_ENV_PATCH = None


def setUpModule():
    global _ENV_PATCH
    home = tempfile.mkdtemp()
    empty = os.path.join(home, "gitconfig")
    open(empty, "w").close()
    _ENV_PATCH = mock.patch.dict(os.environ, {
        "GIT_CONFIG_GLOBAL": empty, "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com",
        "XDG_STATE_HOME": os.path.join(home, "state"),
    })
    _ENV_PATCH.start()
    setUpModule.home = home


def tearDownModule():
    _ENV_PATCH.stop()
    shutil.rmtree(setUpModule.home, ignore_errors=True)


def git(cwd, *args):
    p = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if p.returncode != 0:
        raise AssertionError(f"git {' '.join(args)}: {p.stderr}")
    return p.stdout.strip()


def write(path, text=""):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def age(path, days):
    """Set the mtime of path and everything inside it to days ago."""
    t = time.time() - days * 86400
    for dirpath, dirnames, filenames in os.walk(path):
        for name in dirnames + filenames:
            os.utime(os.path.join(dirpath, name), (t, t), follow_symlinks=False)
    os.utime(path, (t, t))


def sid(name):
    """A session id (UUID) derived from a readable test name."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, name))


def dead_pid():
    p = subprocess.Popen([sys.executable, "-c", "pass"])
    p.wait()
    return p.pid


class Base(unittest.TestCase):
    """A primary checkout with an origin bare repo and a second clone that merges on origin."""

    def setUp(self):
        self.tmp = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.origin = os.path.join(self.tmp, "origin.git")
        self.repo = os.path.join(self.tmp, "proj")
        self.other = os.path.join(self.tmp, "other")
        self.scratch = os.path.join(self.tmp, "claude-1000")
        self.sessions = os.path.join(self.tmp, "sessions")
        self.state = os.path.join(self.tmp, "state")
        for d in (self.scratch, self.sessions):
            os.makedirs(d)
        git(self.tmp, "init", "-q", "--bare", "-b", "main", self.origin)
        git(self.tmp, "init", "-q", "-b", "main", self.repo)
        write(os.path.join(self.repo, ".gitignore"), ".env\ndist/\nnode_modules/\n")
        self.commit(self.repo, "init")
        git(self.repo, "remote", "add", "origin", self.origin)
        git(self.repo, "push", "-q", "-u", "origin", "main")
        git(self.tmp, "clone", "-q", self.origin, self.other)

    def commit(self, cwd, name):
        write(os.path.join(cwd, f"{name}.txt"), name)
        git(cwd, "add", "-A")
        git(cwd, "commit", "-q", "-m", name)
        return git(cwd, "rev-parse", "HEAD")

    def branch(self, name, commits=1, push=True):
        """Create branch name in the primary checkout with commits, then switch back to main."""
        git(self.repo, "checkout", "-q", "-b", name)
        tip = None
        for i in range(commits):
            tip = self.commit(self.repo, f"{name.replace('/', '_')}-{i}")
        if push:
            git(self.repo, "push", "-q", "origin", name)
        git(self.repo, "checkout", "-q", "main")
        return tip

    def merge_on_origin(self, name, how="merge"):
        git(self.other, "fetch", "-q", "origin")
        git(self.other, "checkout", "-q", "main")
        git(self.other, "reset", "-q", "--hard", "origin/main")
        if how == "merge":
            git(self.other, "merge", "-q", "--no-ff", "-m", f"merge {name}", f"origin/{name}")
        elif how == "squash":
            git(self.other, "merge", "-q", "--squash", f"origin/{name}")
            git(self.other, "commit", "-q", "-m", f"squash {name}")
        elif how == "rebase":
            self.commit(self.other, f"diverge-{name.replace('/', '_')}")
            shas = git(self.other, "rev-list", "--reverse", f"origin/main..origin/{name}").split()
            for sha in shas:
                git(self.other, "cherry-pick", sha)
        git(self.other, "push", "-q", "origin", "main")

    def ctx(self, repo=None, **kw):
        kw.setdefault("platform", None)
        kw.setdefault("cwd", repo or self.repo)
        return c.Context(repo or self.repo, scratch_root=self.scratch, sessions_dir=self.sessions,
                         state_dir=self.state, **kw)

    def scan(self, **kw):
        ctx = self.ctx(**kw)
        lines, data = c.scan(ctx)
        return ctx, lines, data

    def items(self, data, kind):
        return {i["target"]: i for i in data["items"] if i["kind"] == kind}

    def stub_gh(self, prs):
        bin_dir = os.path.join(self.tmp, "bin")
        os.makedirs(bin_dir, exist_ok=True)
        payload = os.path.join(self.tmp, "gh.json")
        write(payload, json.dumps(prs))
        write(os.path.join(bin_dir, "gh"), f"#!/bin/sh\ncat '{payload}'\n")
        os.chmod(os.path.join(bin_dir, "gh"), 0o755)
        patch = mock.patch.dict(os.environ, {"PATH": bin_dir + os.pathsep + os.environ["PATH"]})
        patch.start()
        self.addCleanup(patch.stop)

    def add_worktree(self, name, branch=None, new=False):
        path = os.path.join(self.tmp, "proj.worktrees", name)
        args = ["worktree", "add", "-q"]
        if new:
            args += ["-b", branch, path]
        elif branch:
            args += [path, branch]
        else:
            args += ["--detach", path, "origin/main"]
        git(self.repo, *args)
        return path

    def session(self, project, name, files=(), days=10):
        path = os.path.join(self.scratch, project, sid(name))
        os.makedirs(os.path.join(path, "scratchpad"))
        write(os.path.join(path, "started"))
        for rel in files:
            write(os.path.join(path, rel), "x" * 10)
        age(path, days)
        return path


# ---------------------------------------------------------------- 1. merge detection and branches


class MergeDetection(Base):
    def test_regular_merge(self):
        self.branch("feat/a")
        self.merge_on_origin("feat/a")
        _, _, data = self.scan()
        self.assertIn("in origin/main", self.items(data, "b")["feat/a"]["why"])
        self.assertEqual(self.items(data, "b")["feat/a"]["cls"], "safe")

    def test_stale_local_main(self):
        self.branch("feat/a")
        self.merge_on_origin("feat/a")
        _, _, data = self.scan()
        self.assertNotEqual(git(self.repo, "rev-parse", "main"), git(self.repo, "rev-parse", "origin/main"))
        self.assertIn("feat/a", self.items(data, "b"))

    def test_squash_with_gh(self):
        tip = self.branch("feat/sq", commits=2)
        self.merge_on_origin("feat/sq", "squash")
        self.stub_gh([{"number": 7, "headRefName": "feat/sq", "headRefOid": tip}])
        _, _, data = self.scan(platform="github")
        item = self.items(data, "b")["feat/sq"]
        self.assertEqual(item["cls"], "safe")
        self.assertIn("PR #7", item["why"])

    def test_squash_without_cli_is_not_listed_and_says_why(self):
        self.branch("feat/sq", commits=2)
        self.merge_on_origin("feat/sq", "squash")
        with mock.patch.object(c.shutil, "which", return_value=None):
            ctx, lines, data = self.scan(platform="github")
        self.assertNotIn("feat/sq", self.items(data, "b"))
        self.assertTrue(any("needs gh or glab" in n for n in ctx.notes))
        self.assertIn("needs gh or glab", "\n".join(lines))

    def test_no_platform_names_skipped_check(self):
        ctx, _, _ = self.scan(platform=None)
        self.assertTrue(any(n.startswith(c.SKIP_SQUASH) for n in ctx.notes))

    def test_rebase_merge_without_cli(self):
        self.branch("feat/rb", commits=2)
        self.merge_on_origin("feat/rb", "rebase")
        _, _, data = self.scan()
        self.assertIn("patch-equivalent", self.items(data, "b")["feat/rb"]["why"])

    def test_reused_branch_is_risky(self):
        tip = self.branch("feat/re")
        self.merge_on_origin("feat/re", "squash")
        git(self.repo, "checkout", "-q", "feat/re")
        self.commit(self.repo, "more")
        git(self.repo, "checkout", "-q", "main")
        self.stub_gh([{"number": 9, "headRefName": "feat/re", "headRefOid": tip}])
        _, _, data = self.scan(platform="github")
        item = self.items(data, "b")["feat/re"]
        self.assertEqual(item["cls"], "risky")
        self.assertIn("1 more commits: more", item["why"])

    def test_reused_branch_names_commit_subjects_capped(self):
        tip = self.branch("feat/many")
        self.merge_on_origin("feat/many", "squash")
        git(self.repo, "checkout", "-q", "feat/many")
        for n in range(7):
            self.commit(self.repo, f"extra-{n}")
        git(self.repo, "checkout", "-q", "main")
        self.stub_gh([{"number": 4, "headRefName": "feat/many", "headRefOid": tip}])
        _, _, data = self.scan(platform="github")
        why = self.items(data, "b")["feat/many"]["why"]
        self.assertIn("7 more commits: extra-6, extra-5, extra-4, extra-3, extra-2 and 2 more", why)


class Branches(Base):
    def test_primary_checkout_branch_is_not_listed(self):
        self.branch("feat/cur")
        self.merge_on_origin("feat/cur")
        git(self.repo, "checkout", "-q", "feat/cur")
        _, _, data = self.scan()
        self.assertNotIn("feat/cur", self.items(data, "b"))

    def test_current_worktree_branch_is_not_listed(self):
        self.branch("feat/wt")
        self.merge_on_origin("feat/wt")
        wt = self.add_worktree("wt", "feat/wt")
        ctx, _, data = self.scan(repo=wt)
        self.assertNotIn("feat/wt", self.items(data, "b"))
        self.assertNotIn(wt, self.items(data, "w"))
        self.assertTrue(any("current worktree" in k for k in ctx.kept))

    def test_protected_patterns(self):
        for name in ("develop", "release/1.0", "trunk", "master"):
            self.branch(name)
            self.merge_on_origin(name)
        _, _, data = self.scan()
        self.assertEqual(self.items(data, "b"), {})
        self.assertEqual(self.items(data, "r"), {})

    def test_release_please_branch_is_listed(self):
        name = "release-please--branches--main--components--base"
        self.branch(name)
        self.merge_on_origin(name)
        _, _, data = self.scan()
        self.assertIn(name, self.items(data, "b"))
        self.assertIn(name, self.items(data, "r"))

    def test_open_pr_branch_is_not_listed(self):
        self.branch("feat/open")
        _, _, data = self.scan()
        self.assertNotIn("feat/open", self.items(data, "b"))
        self.assertNotIn("feat/open", self.items(data, "r"))

    def test_remote_branch_shows_pr_number(self):
        tip = self.branch("fix/some-bug")
        self.merge_on_origin("fix/some-bug")
        self.stub_gh([{"number": 12, "headRefName": "fix/some-bug", "headRefOid": tip}])
        _, _, data = self.scan(platform="github")
        self.assertIn("PR #12", self.items(data, "r")["fix/some-bug"]["why"])


# ---------------------------------------------------------------- 2. worktrees and orphans


class Worktrees(Base):
    def merged_worktree(self, name="wt"):
        self.branch(f"feat/{name}")
        self.merge_on_origin(f"feat/{name}")
        return self.add_worktree(name, f"feat/{name}")

    def test_clean_merged_worktree_is_safe(self):
        wt = self.merged_worktree()
        _, _, data = self.scan()
        item = self.items(data, "w")[wt]
        self.assertEqual(item["cls"], "safe")
        self.assertEqual(item["branch"], "feat/wt")

    def test_untracked_file_is_risky(self):
        wt = self.merged_worktree()
        write(os.path.join(wt, "notes.txt"), "x")
        _, _, data = self.scan()
        item = self.items(data, "w")[wt]
        self.assertEqual(item["cls"], "risky")
        self.assertIn("1 changed or untracked files: notes.txt", item["why"])

    def test_unpushed_commits_without_pr_are_not_listed(self):
        wt = self.merged_worktree()
        self.commit(wt, "unpushed")
        _, _, data = self.scan()
        self.assertNotIn(wt, self.items(data, "w"))

    def test_commits_after_merged_pr_are_risky(self):
        self.branch("feat/re")
        self.merge_on_origin("feat/re", "squash")
        tip = git(self.repo, "rev-parse", "feat/re")
        wt = self.add_worktree("re", "feat/re")
        self.commit(wt, "after")
        self.stub_gh([{"number": 3, "headRefName": "feat/re", "headRefOid": tip}])
        _, _, data = self.scan(platform="github")
        item = self.items(data, "w")[wt]
        self.assertEqual(item["cls"], "risky")
        self.assertIn("1 more commits: after", item["why"])

    def test_locked_worktree_is_kept(self):
        wt = self.merged_worktree()
        git(self.repo, "worktree", "lock", wt)
        ctx, _, data = self.scan()
        self.assertNotIn(wt, self.items(data, "w"))
        self.assertTrue(any("locked" in k for k in ctx.kept))

    def test_worktree_in_use_by_session_names_it(self):
        wt = self.merged_worktree()
        write(os.path.join(self.sessions, "1.json"),
              json.dumps({"pid": os.getpid(), "sessionId": "live-1", "cwd": wt}))
        ctx, _, data = self.scan()
        self.assertNotIn(wt, self.items(data, "w"))
        self.assertTrue(any("live-1" in k for k in ctx.kept))

    def test_identical_ignored_env_is_safe(self):
        wt = self.merged_worktree()
        write(os.path.join(self.repo, ".env"), "A=1\n")
        write(os.path.join(wt, ".env"), "A=1\n")
        _, _, data = self.scan()
        self.assertEqual(self.items(data, "w")[wt]["cls"], "safe")

    def test_different_ignored_env_is_risky(self):
        wt = self.merged_worktree()
        write(os.path.join(self.repo, ".env"), "A=1\n")
        write(os.path.join(wt, ".env"), "A=2\n")
        _, _, data = self.scan()
        item = self.items(data, "w")[wt]
        self.assertEqual(item["cls"], "risky")
        self.assertIn(".env", item["why"])

    def test_missing_ignored_env_is_risky(self):
        wt = self.merged_worktree()
        write(os.path.join(wt, ".env"), "A=2\n")
        _, _, data = self.scan()
        self.assertEqual(self.items(data, "w")[wt]["cls"], "risky")

    def test_only_build_output_is_safe(self):
        wt = self.merged_worktree()
        write(os.path.join(wt, "dist", "app.js"), "x")
        write(os.path.join(wt, "node_modules", "x", "index.js"), "x")
        _, _, data = self.scan()
        self.assertEqual(self.items(data, "w")[wt]["cls"], "safe")

    def test_detached_worktree_in_origin_main_is_safe(self):
        wt = self.add_worktree("det")
        _, _, data = self.scan()
        item = self.items(data, "w")[wt]
        self.assertEqual(item["cls"], "safe")
        self.assertIsNone(item["branch"])

    def test_dangling_worktree(self):
        wt = self.merged_worktree()
        shutil.rmtree(wt)
        _, _, data = self.scan()
        self.assertTrue(self.items(data, "w")[wt]["dangling"])


class Orphans(Base):
    def test_orphan_folder_is_risky(self):
        self.branch("feat/o")
        wt = self.add_worktree("o", "feat/o")
        shutil.rmtree(os.path.join(self.repo, ".git", "worktrees", "o"))
        _, _, data = self.scan()
        self.assertEqual(self.items(data, "o")[wt]["cls"], "risky")

    def test_sibling_repository_is_unknown(self):
        sibling = os.path.join(self.tmp, "proj-backend")
        git(self.tmp, "init", "-q", sibling)
        plain = os.path.join(self.tmp, "proj.worktrees", "notes")
        os.makedirs(plain)
        ctx, _, data = self.scan()
        self.assertEqual(self.items(data, "o"), {})
        self.assertIn(sibling, ctx.unknown)
        self.assertIn(plain, ctx.unknown)


# ---------------------------------------------------------------- 3. sessions and scratch folders


class Liveness(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.proc = os.path.join(self.tmp, "proc")
        fields = ["S"] + ["0"] * 18 + ["12345"]  # field 22 is the 20th after the command name
        write(os.path.join(self.proc, str(os.getpid()), "stat"), f"{os.getpid()} (py thon) " + " ".join(fields))

    def test_live_pid_with_matching_start(self):
        self.assertTrue(c.is_running({"pid": os.getpid(), "procStart": "12345"}, self.proc))

    def test_start_stored_as_number_is_compared_as_string(self):
        self.assertTrue(c.is_running({"pid": os.getpid(), "procStart": 12345}, self.proc))

    def test_dead_pid(self):
        self.assertFalse(c.is_running({"pid": dead_pid(), "procStart": "12345"}, self.proc))

    def test_reused_pid(self):
        self.assertFalse(c.is_running({"pid": os.getpid(), "procStart": "999"}, self.proc))

    def test_no_start_time_and_pid_exists_counts_as_running(self):
        self.assertTrue(c.is_running({"pid": os.getpid()}, self.proc))

    def test_no_proc_counts_existing_pid_as_running(self):
        self.assertTrue(c.is_running({"pid": os.getpid(), "procStart": "999"}, os.path.join(self.tmp, "none")))

    def test_key_and_broken_files_are_skipped(self):
        d = os.path.join(self.tmp, "sessions")
        write(os.path.join(d, "1.json"), json.dumps({"pid": 1, "sessionId": "a"}))
        write(os.path.join(d, "2.abc.key"), "secret")
        write(os.path.join(d, "3.json"), "{broken")
        self.assertEqual([r["sessionId"] for r in c.read_sessions(d)], ["a"])


class ScratchFolders(Base):
    def setUp(self):
        super().setUp()
        self.project = c.encode(self.repo)

    def test_empty_folders_are_one_safe_group(self):
        self.session(self.project, "s-a")
        a = os.path.join(self.scratch, self.project, sid("s-b"))
        os.makedirs(os.path.join(a, "tasks", "deep"))
        write(os.path.join(a, "started"))
        age(a, 10)
        _, _, data = self.scan()
        group = [i for i in data["items"] if i.get("group")]
        self.assertEqual(len(group), 1)
        self.assertEqual(group[0]["cls"], "safe")
        self.assertEqual(len(group[0]["paths"]), 2)

    def test_task_output_is_risky(self):
        path = self.session(self.project, "s-t", files=["tasks/out.output"])
        _, _, data = self.scan()
        item = self.items(data, "s")[path]
        self.assertEqual(item["cls"], "risky")
        self.assertIn("tasks/out.output", item["why"])

    def test_zero_byte_file_is_risky(self):
        path = os.path.join(self.scratch, self.project, sid("s-z"))
        write(os.path.join(path, "scratchpad", "empty.txt"))
        age(path, 10)
        _, _, data = self.scan()
        self.assertEqual(self.items(data, "s")[path]["cls"], "risky")

    def test_folder_not_named_by_session_id_is_ignored(self):
        path = os.path.join(self.scratch, self.project, "tasks")
        os.makedirs(path)
        age(path, 30)
        _, _, data = self.scan()
        self.assertEqual(data["items"], [])

    def test_recent_file_is_not_listed(self):
        path = self.session(self.project, "s-r")
        write(os.path.join(path, "scratchpad", "new.txt"), "x")
        _, _, data = self.scan()
        self.assertEqual(self.items(data, "s"), {})

    def test_running_session_is_not_listed(self):
        self.session(self.project, "s-live")
        write(os.path.join(self.sessions, "1.json"), json.dumps({"pid": os.getpid(), "sessionId": sid("s-live")}))
        _, _, data = self.scan()
        self.assertEqual(self.items(data, "s"), {})

    def test_stale_folder_without_session_file_is_listed(self):
        self.session(self.project, "s-none")
        _, _, data = self.scan()
        self.assertEqual(len(data["items"]), 1)

    def test_days_option(self):
        self.session(self.project, "s-3", days=3)
        _, _, data = self.scan()
        self.assertEqual(data["items"], [])
        _, _, data = self.scan(days=2)
        self.assertEqual(len(data["items"]), 1)

    def test_sibling_repo_folder_is_out_of_scope(self):
        self.session(self.project + "-template", "s-sib")
        _, _, data = self.scan()
        self.assertEqual(data["items"], [])

    def test_subfolder_session_is_in_scope(self):
        os.makedirs(os.path.join(self.repo, "docs", "my_notes"))
        self.session(self.project + "-docs-my-notes", "s-sub")
        _, _, data = self.scan()
        self.assertEqual(len(data["items"]), 1)

    def test_worktree_project_folder_is_in_scope(self):
        self.branch("feat/x", push=False)
        wt = self.add_worktree("x", "feat/x")
        self.session(c.encode(wt), "s-wt")
        _, _, data = self.scan()
        self.assertEqual(len(self.items(data, "s")), 1)

    def test_other_project_needs_all_projects(self):
        self.session("-other-proj", "s-o")
        _, _, data = self.scan()
        self.assertEqual(data["items"], [])
        _, _, data = self.scan(all_projects=True)
        self.assertEqual(len(data["items"]), 1)

    def test_non_project_folders_are_never_read(self):
        for name in ("node-compile-cache", "bundled-skills"):
            path = os.path.join(self.scratch, name, "old")
            write(os.path.join(path, "file"), "x")
            age(path, 30)
        with mock.patch.object(c, "inspect_folder", wraps=c.inspect_folder) as spy:
            _, _, data = self.scan(all_projects=True)
        self.assertEqual(data["items"], [])
        self.assertEqual(spy.call_count, 0)

    def test_folders_outside_the_scratch_root_are_not_read(self):
        stand_in = os.path.join(self.tmp, "fake-tmp")
        old = os.path.join(stand_in, "tmp.AbCd123456")
        write(os.path.join(old, "f"), "x")
        age(old, 30)
        self.scratch = os.path.join(stand_in, "claude-1000")
        self.session(self.project, "s-in")
        seen = []
        real_walk = os.walk
        with mock.patch.object(c.os, "walk", side_effect=lambda p, *a, **k: seen.append(p) or real_walk(p, *a, **k)):
            _, _, data = self.scan(all_projects=True)
        self.assertEqual(len(data["items"]), 1)
        self.assertFalse([p for p in seen if p.startswith(old)])

    def test_symlink_is_removed_target_kept(self):
        target = os.path.join(self.tmp, "outside")
        write(os.path.join(target, "keep.txt"), "keep")
        path = self.session(self.project, "s-link")
        os.symlink(target, os.path.join(path, "scratchpad", "link"))
        age(path, 10)
        ctx, _, data = self.scan()
        item = self.items(data, "s")[path]
        self.assertEqual(item["cls"], "risky")
        c.remove(self.ctx(fetch=False), data, [], [item["id"]], apply=True)
        self.assertFalse(os.path.exists(path))
        self.assertTrue(os.path.isfile(os.path.join(target, "keep.txt")))


class OwnLeftovers(Base):
    def test_only_mktemp_shaped_folders_are_listed_first(self):
        pad = os.path.join(self.scratch, c.encode(self.repo), "s-own", "scratchpad")
        os.makedirs(os.path.join(pad, "tmp.Ab12Cd34Ef"))
        os.makedirs(os.path.join(pad, "explore"))
        write(os.path.join(pad, "notes.md"), "x")
        cwd = os.path.join(pad, "tmp.Zz98Yy76Xx")
        os.makedirs(cwd)
        self.session(c.encode(self.repo), "s-old")
        _, _, data = self.scan(own=pad, cwd=cwd)
        own = [i for i in data["items"] if i["kind"] == "m"]
        self.assertEqual([i["target"] for i in own], ["tmp.Ab12Cd34Ef"])
        self.assertEqual(data["items"][0]["id"], "m1")

    def test_mktemp_shape(self):
        for name in ("tmp.Ab12Cd34Ef", "tmp.abcdef", "fixture.Xy12ab", "repo-aB3dE9"):
            self.assertTrue(c.mktemp_shaped(name), name)
        for name in ("explore", "notes.md", "build-output", "tmp.ab", "results"):
            self.assertFalse(c.mktemp_shaped(name), name)

    def test_scratch_root_follows_own(self):
        root = f"/tmp/claude-{os.getuid()}"
        pad = os.path.join(root, "-p", sid("own"), "scratchpad")  # not created: only the path is read
        self.assertEqual(c.default_scratch_root(pad), root)

    def test_scratch_root_outside_tmp_claude_is_ignored(self):
        pad = os.path.join(self.scratch, "-p", "sid", "scratchpad")
        os.makedirs(pad)
        self.assertEqual(c.default_scratch_root(pad), f"/tmp/claude-{os.getuid()}")


# ---------------------------------------------------------------- 4. output, removal and log


class Output(Base):
    def run_cli(self, *args):
        env = dict(os.environ, XDG_STATE_HOME=self.state)
        return subprocess.run([sys.executable, SCRIPT, *args, "--repo", self.repo, "--scratch-root", self.scratch,
                               "--sessions-dir", self.sessions], capture_output=True, text=True, env=env)

    def test_nothing_to_clean_prints_one_line(self):
        p = self.run_cli("scan")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(len(p.stdout.strip().splitlines()), 1)
        self.assertTrue(p.stdout.startswith("Nothing to clean."))

    def test_large_state_is_capped(self):
        project = c.encode(self.repo)
        for n in range(45):
            self.session(project, f"s-{n:02d}", files=["scratchpad/f.txt"], days=10 + n)
        _, lines, data = self.scan()
        rows = [line for line in lines if re.match(r"^  s\d+ ", line)]
        self.assertEqual(len(rows), c.TABLE_CAP)
        self.assertIn(sid("s-44")[:8], rows[0])  # oldest first
        self.assertIn("5 more items not shown", lines[-1])
        with open(os.path.join(self.state, "last-scan.json")) as f:
            self.assertEqual(len(json.load(f)["items"]), 45)
        self.assertLessEqual(len(lines), c.TABLE_CAP + 10)

    def test_log_remote_cli(self):
        tip = self.branch("fix/b")
        self.merge_on_origin("fix/b")
        self.assertEqual(self.run_cli("scan").returncode, 0)
        p = self.run_cli("log-remote", "--ids", "r1")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stdout.splitlines()[-1], f"  git -C {self.repo} push origin --delete fix/b")
        with open(os.path.join(self.state, "claude-cleanup", "cleanup.log")) as f:
            entry = json.loads(f.readline())
        self.assertEqual((entry["target"], entry["tip"]), ("fix/b", tip))
        self.assertIn("fix/b", git(self.origin, "branch"))

    def test_cap_keeps_oldest_across_groups(self):
        self.branch("feat/new")
        self.merge_on_origin("feat/new")
        project = c.encode(self.repo)
        for n in range(40):
            self.session(project, f"s-{n:02d}", files=["scratchpad/f.txt"], days=10 + n)
        _, lines, data = self.scan()
        self.assertEqual(len([line for line in lines if re.match(r"^  [a-z]\d+ ", line)]), c.TABLE_CAP)
        self.assertNotIn("feat/new", "\n".join(lines[:-1]))  # the youngest items (b1, r1) are cut
        self.assertIn("2 more items not shown", lines[-1])
        self.assertIn("feat/new", self.items(data, "b"))

    def test_scan_deletes_nothing(self):
        self.branch("feat/a")
        self.merge_on_origin("feat/a")
        path = self.session(c.encode(self.repo), "s-x")
        self.scan()
        self.assertTrue(os.path.isdir(path))
        self.assertIn("feat/a", git(self.repo, "branch"))


class Removal(Base):
    def read_log(self):
        with open(os.path.join(self.state, "cleanup.log")) as f:
            return [json.loads(line) for line in f]

    def merged_worktree(self):
        self.branch("feat/wt")
        self.merge_on_origin("feat/wt")
        return self.add_worktree("wt", "feat/wt")

    def ids(self, data, kind):
        return [i["id"] for i in data["items"] if i["kind"] == kind]

    def test_dry_run_deletes_nothing(self):
        self.branch("feat/a")
        self.merge_on_origin("feat/a")
        wt = self.merged_worktree()
        path = self.session(c.encode(self.repo), "s-x")
        self.session(c.encode(self.repo), "s-y")
        _, _, data = self.scan()
        lines = c.remove(self.ctx(fetch=False), data, [i["id"] for i in data["items"] if i["kind"] != "r"], [], apply=False)
        self.assertEqual([line for line in lines if " s1" in line], ["Would remove s1: 2 of 2 empty session folders"])
        self.assertTrue(os.path.isdir(wt) and os.path.isdir(path))
        self.assertIn("feat/a", git(self.repo, "branch"))
        self.assertIn("Nothing was deleted", lines[-1])
        self.assertFalse(os.path.exists(os.path.join(self.state, "cleanup.log")))

    def test_worktree_dirty_after_scan_is_skipped(self):
        wt = self.merged_worktree()
        _, _, data = self.scan()
        write(os.path.join(wt, "late.txt"), "x")
        lines = c.remove(self.ctx(fetch=False), data, self.ids(data, "w"), [], apply=True)
        self.assertTrue(os.path.isdir(wt))
        self.assertTrue(any("changed since the scan" in line for line in lines))

    def test_refused_worktree_remove_is_reported(self):
        wt = self.merged_worktree()
        _, _, data = self.scan()
        real = c.git

        def refuse(repo, *args):
            if args[:2] == ("worktree", "remove"):
                return subprocess.CompletedProcess(args, 128, "", "fatal: refused for the test")
            return real(repo, *args)

        with mock.patch.object(c, "git", side_effect=refuse):
            lines = c.remove(self.ctx(fetch=False), data, self.ids(data, "w"), [], apply=True)
        self.assertTrue(os.path.isdir(wt))
        self.assertTrue(any("git refused: fatal: refused for the test" in line for line in lines))
        self.assertEqual(self.read_log()[0]["result"], "skipped")

    def worktree_remove_calls(self, spy):
        return [call.args[0] for call in spy.call_args_list if call.args[0][3:5] == ["worktree", "remove"]]

    def test_safe_worktree_is_never_forced(self):
        wt = self.merged_worktree()
        _, _, data = self.scan()
        with mock.patch.object(c.subprocess, "run", wraps=c.subprocess.run) as spy:
            c.remove(self.ctx(fetch=False), data, self.ids(data, "w"), [], apply=True)
        self.assertFalse(os.path.exists(wt))
        calls = self.worktree_remove_calls(spy)
        self.assertEqual(len(calls), 1)
        self.assertNotIn("--force", calls[0])

    def test_dirty_worktree_without_own_yes_is_kept(self):
        wt = self.merged_worktree()
        write(os.path.join(wt, "dirty.txt"), "x")
        _, _, data = self.scan()
        lines = c.remove(self.ctx(fetch=False), data, self.ids(data, "w"), [], apply=True)
        self.assertTrue(os.path.isfile(os.path.join(wt, "dirty.txt")))
        self.assertTrue(any("needs its own yes" in line for line in lines))

    def test_dirty_worktree_with_own_yes_is_forced(self):
        wt = self.merged_worktree()
        write(os.path.join(wt, "dirty.txt"), "x")
        write(os.path.join(wt, "init.txt"), "changed")
        _, _, data = self.scan()
        item = self.items(data, "w")[wt]
        self.assertIn("2 changed or untracked files: init.txt, dirty.txt", item["why"])
        with mock.patch.object(c.subprocess, "run", wraps=c.subprocess.run) as spy:
            lines = c.remove(self.ctx(fetch=False), data, [], [item["id"]], apply=True)
        self.assertFalse(os.path.exists(wt))
        self.assertIn("--force", self.worktree_remove_calls(spy)[0])
        self.assertNotIn("feat/wt", git(self.repo, "branch"))
        self.assertTrue(any("forced" in line for line in lines))
        self.assertEqual(self.read_log()[0]["detail"], "forced, changed files deleted")

    def test_approved_dirty_worktree_that_changed_again_is_kept(self):
        wt = self.merged_worktree()
        write(os.path.join(wt, "dirty.txt"), "x")
        _, _, data = self.scan()
        write(os.path.join(wt, "later.txt"), "x")
        lines = c.remove(self.ctx(fetch=False), data, [], self.ids(data, "w"), apply=True)
        self.assertTrue(os.path.isfile(os.path.join(wt, "later.txt")))
        self.assertTrue(any("changed since the scan" in line for line in lines))

    def test_worktree_then_branch(self):
        wt = self.merged_worktree()
        tip = git(self.repo, "rev-parse", "feat/wt")
        _, _, data = self.scan()
        c.remove(self.ctx(fetch=False), data, self.ids(data, "w"), [], apply=True)
        self.assertFalse(os.path.exists(wt))
        self.assertNotIn("feat/wt", git(self.repo, "branch"))
        log = self.read_log()
        self.assertEqual([(e["target"], e["result"]) for e in log],
                         [(wt, "removed"), ("branch feat/wt", "removed")])
        self.assertEqual(log[1]["tip"], tip)

    def test_branch_checked_out_elsewhere_is_kept(self):
        self.branch("feat/a")
        self.merge_on_origin("feat/a")
        _, _, data = self.scan()
        self.add_worktree("later", "feat/a")
        lines = c.remove(self.ctx(fetch=False), data, self.ids(data, "b"), [], apply=True)
        self.assertIn("feat/a", git(self.repo, "branch"))
        self.assertTrue(any("checked out in" in line for line in lines))

    def test_branch_log_holds_tip(self):
        tip = self.branch("feat/a")
        self.merge_on_origin("feat/a")
        _, _, data = self.scan()
        c.remove(self.ctx(fetch=False), data, self.ids(data, "b"), [], apply=True)
        entry = self.read_log()[0]
        self.assertEqual((entry["target"], entry["result"], entry["tip"]), ("branch feat/a", "removed", tip))

    def test_session_path_outside_root_is_refused(self):
        outside = os.path.join(self.tmp, "elsewhere", "s-out")
        write(os.path.join(outside, "f"), "x")
        link_project = os.path.join(self.scratch, "-linked")
        os.makedirs(link_project)
        os.symlink(outside, os.path.join(link_project, "s-link"))
        data = {"items": [
            {"id": "s1", "kind": "s", "target": outside, "path": outside, "cls": "risky", "why": ""},
            {"id": "s2", "kind": "s", "target": "x", "path": os.path.join(link_project, "s-link"),
             "cls": "risky", "why": ""},
        ]}
        lines = c.remove(self.ctx(fetch=False), data, [], ["s1", "s2"], apply=True)
        self.assertTrue(os.path.isfile(os.path.join(outside, "f")))
        self.assertTrue(any("outside the scratch root" in line for line in lines))
        self.assertTrue(any("symlink" in line for line in lines))

    def test_session_folder_removed_whole(self):
        path = self.session(c.encode(self.repo), "s-x")
        os.makedirs(os.path.join(path, "tasks"))
        age(path, 10)
        _, _, data = self.scan()
        c.remove(self.ctx(fetch=False), data, ["s1"], [], apply=True)
        self.assertFalse(os.path.exists(path))
        self.assertEqual(self.read_log()[0]["result"], "removed")

    def test_risky_without_own_yes_is_skipped(self):
        path = self.session(c.encode(self.repo), "s-f", files=["scratchpad/a.txt"])
        _, _, data = self.scan()
        lines = c.remove(self.ctx(fetch=False), data, self.ids(data, "s"), [], apply=True)
        self.assertTrue(os.path.isdir(path))
        self.assertTrue(any("needs its own yes" in line for line in lines))

    def test_session_that_started_again_is_skipped(self):
        path = self.session(c.encode(self.repo), "s-back")
        _, _, data = self.scan()
        write(os.path.join(self.sessions, "1.json"), json.dumps({"pid": os.getpid(), "sessionId": sid("s-back")}))
        c.remove(self.ctx(fetch=False), data, ["s1"], [], apply=True)
        self.assertTrue(os.path.isdir(path))

    def test_own_leftover_removed(self):
        pad = os.path.join(self.scratch, c.encode(self.repo), "s-own", "scratchpad")
        tmp = os.path.join(pad, "tmp.Ab12Cd34Ef")
        write(os.path.join(tmp, "stub.sh"), "x")
        _, _, data = self.scan(own=pad)
        c.remove(self.ctx(fetch=False, own=pad), data, ["m1"], [], apply=True)
        self.assertFalse(os.path.exists(tmp))
        self.assertTrue(os.path.isdir(pad))

    def test_unknown_id_is_an_error(self):
        _, _, data = self.scan()
        with self.assertRaises(c.Error):
            c.remove(self.ctx(fetch=False), data, ["b9"], [], apply=False)


class NeverPushes(Base):
    def test_source_has_no_push_call(self):
        with open(SCRIPT, encoding="utf-8") as f:
            src = f.read()
        self.assertNotRegex(src, r"""["']push["']""")
        self.assertNotIn("gh api", src)

    def test_log_remote_logs_tips_and_only_prints_the_push(self):
        name = "release-please--branches--main--components--base"
        tips = {name: self.branch(name), "fix/b": self.branch("fix/b")}
        for n in (name, "fix/b"):
            self.merge_on_origin(n)
        _, _, data = self.scan()
        with mock.patch.object(c.subprocess, "run", wraps=c.subprocess.run) as spy:
            lines = c.log_remote(self.ctx(fetch=False), data, self.ids(data))
        self.assertIn(f"git -C {self.repo} push origin --delete", lines[-1])
        self.assertIn(name, lines[-1])
        self.assertFalse([call for call in spy.call_args_list if "push" in call.args[0]])
        remote = git(self.origin, "branch")
        self.assertIn("fix/b", remote)
        self.assertIn(name, remote)
        with open(os.path.join(self.state, "cleanup.log")) as f:
            log = [json.loads(line) for line in f]
        self.assertEqual({(e["target"], e["tip"], e["result"]) for e in log},
                         {(n, t, "push-approved") for n, t in tips.items()})

    def test_log_remote_skips_a_branch_that_moved(self):
        self.branch("fix/b")
        self.merge_on_origin("fix/b")
        _, _, data = self.scan()
        git(self.repo, "checkout", "-q", "fix/b")
        self.commit(self.repo, "later")
        git(self.repo, "push", "-q", "origin", "fix/b")
        git(self.repo, "checkout", "-q", "main")
        lines = c.log_remote(self.ctx(fetch=False), data, self.ids(data))
        self.assertEqual(lines[-1], "No remote branches to delete.")
        self.assertTrue(any("moved on origin" in line for line in lines))

    def test_remove_refuses_remote_ids(self):
        self.branch("fix/b")
        self.merge_on_origin("fix/b")
        _, _, data = self.scan()
        with self.assertRaises(c.Error):
            c.remove(self.ctx(fetch=False), data, self.ids(data), [], apply=True)

    def ids(self, data):
        return [i["id"] for i in data["items"] if i["kind"] == "r"]


if __name__ == "__main__":
    unittest.main()

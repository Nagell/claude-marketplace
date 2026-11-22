#!/usr/bin/env python3
"""Find and remove leftovers of finished work.

Leftovers are merged branches, worktrees of merged work, orphan worktree
folders and Claude scratch folders of sessions that are no longer running.

  scan    lists candidates, writes last-scan.json and deletes nothing.
  remove  removes approved ids from the last scan. Dry run unless --apply.

The script never pushes. For remote branches it prints the push command, so
the push goes through the safety-guards hook like any other push.
Standard library only. Python 3.9 or newer.
"""

from __future__ import annotations

import argparse
import filecmp
import fnmatch
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import time
from urllib.parse import urlparse

PROTECTED = ["main", "master", "develop", "trunk", "release/*"]
BUILD_DIRS = {"node_modules", "dist", ".nuxt", ".output", "build", "coverage", "__pycache__"}
TABLE_CAP = 40
LIST_CAP = 5
GROUPS = [
    ("m", "Own session leftovers"),
    ("b", "Local branches"),
    ("r", "Remote branches (one push, asked separately)"),
    ("w", "Worktrees"),
    ("o", "Orphan worktree folders"),
    ("s", "Session scratch folders"),
]
SKIP_SQUASH = "squash merge check skipped: needs gh or glab"
SESSION_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
MKTEMP_RE = re.compile(r"^tmp\.[A-Za-z0-9]{6,}$")
SUFFIX_RE = re.compile(r"[.-]([A-Za-z0-9]{6,})$")


class Error(Exception):
    pass


# ---------------------------------------------------------------- helpers


def run(args, cwd=None):
    try:
        return subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    except FileNotFoundError:
        return subprocess.CompletedProcess(args, 127, "", f"{args[0]}: not found")


def git(repo, *args):
    return run(["git", "-C", repo, *args])


def git_out(repo, *args):
    p = git(repo, *args)
    if p.returncode != 0:
        raise Error(f"git {' '.join(args)} failed: {p.stderr.strip()}")
    return p.stdout.strip()


def encode(path):
    """Claude's project folder name for a working directory."""
    return re.sub(r"[/_.]", "-", path)


def default_state_dir():
    base = os.environ.get("XDG_STATE_HOME") or os.path.join(os.path.expanduser("~"), ".local", "state")
    return os.path.join(base, "claude-cleanup")


def default_scratch_root(own=None):
    """The scratch root, from the scratchpad path when given (<root>/<project>/<session>/scratchpad)."""
    if own:
        parts = os.path.realpath(own).split(os.sep)
        if len(parts) >= 4 and parts[-3].startswith("-"):
            return os.sep.join(parts[:-3])
    return f"/tmp/claude-{os.getuid()}"


def human(size):
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size} B"


def capped(names, limit=LIST_CAP):
    names = list(names)
    text = ", ".join(names[:limit])
    return text + (f" and {len(names) - limit} more" if len(names) > limit else "")


def inside(path, root):
    path, root = os.path.realpath(path), os.path.realpath(root)
    return path == root or path.startswith(root + os.sep)


def mktemp_shaped(name):
    """True for names that mktemp -d produces: tmp.XXXXXXXXXX or <prefix>.<random>."""
    if MKTEMP_RE.match(name):
        return True
    m = SUFFIX_RE.search(name)
    if not m:
        return False
    s = m.group(1)
    kinds = [any(c.islower() for c in s), any(c.isupper() for c in s), any(c.isdigit() for c in s)]
    return sum(kinds) >= 2


# ---------------------------------------------------------------- sessions


def read_sessions(sessions_dir):
    records = []
    try:
        names = sorted(os.listdir(sessions_dir))
    except OSError:
        return records
    for name in names:
        if not name.endswith(".json"):
            continue
        try:
            with open(os.path.join(sessions_dir, name), encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            continue
        if isinstance(data, dict) and isinstance(data.get("pid"), int):
            records.append(data)
    return records


def pid_exists(pid):
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def proc_start(pid, proc_root):
    try:
        with open(os.path.join(proc_root, str(pid), "stat"), encoding="utf-8") as f:
            data = f.read()
    except OSError:
        return None
    fields = data.rsplit(")", 1)[-1].split()
    # Field 22 (start time); fields after the command name start at field 3.
    return fields[19] if len(fields) > 19 else None


def is_running(record, proc_root="/proc"):
    """A session runs when its pid exists and, where /proc shows it, its start time matches."""
    pid = record.get("pid")
    if not isinstance(pid, int) or not pid_exists(pid):
        return False
    start = record.get("procStart")
    if start is None or not os.path.isdir(proc_root):
        return True  # cannot prove it stopped: fail safe
    actual = proc_start(pid, proc_root)
    if actual is None:
        return True
    return str(start) == actual


# ---------------------------------------------------------------- context


class Context:
    """Everything a scan or a removal needs to know about the repo and the machine."""

    def __init__(self, repo_path, *, scratch_root=None, sessions_dir=None, state_dir=None, days=7,
                 all_projects=False, own=None, platform="auto", proc_root="/proc", fetch=True,
                 now=None, cwd=None):
        repo_path = os.path.abspath(repo_path)
        self.current = os.path.realpath(git_out(repo_path, "rev-parse", "--show-toplevel"))
        common = git_out(repo_path, "rev-parse", "--git-common-dir")
        if not os.path.isabs(common):
            common = os.path.join(repo_path, common)
        self.common_dir = os.path.realpath(common)
        self.primary = os.path.dirname(self.common_dir)
        self.own = os.path.realpath(own) if own else None
        self.scratch_root = os.path.realpath(scratch_root or default_scratch_root(own))
        self.sessions_dir = sessions_dir or os.path.join(os.path.expanduser("~"), ".claude", "sessions")
        self.state_dir = state_dir or default_state_dir()
        self.days = days
        self.all_projects = all_projects
        self.proc_root = proc_root
        self.now = now if now is not None else time.time()
        self.cwd = os.path.realpath(cwd or os.getcwd())
        self.protected_paths = {self.primary, self.current}
        self.notes = []  # skipped checks
        self.kept = []  # items that are never removable, with the reason
        self.unknown = []  # folders reported, never deleted

        self.has_origin = git(self.primary, "remote", "get-url", "origin").returncode == 0
        if self.has_origin and fetch:
            p = git(self.primary, "fetch", "--prune", "--quiet", "origin")
            if p.returncode != 0:
                self.notes.append(f"fetch of origin failed, using the last fetched refs: {first_line(p.stderr)}")
        self.default = default_branch(self.primary) if self.has_origin else None
        self.base = f"origin/{self.default}" if self.default else None
        if not self.base:
            self.notes.append("no origin default branch: branch and worktree checks skipped")
        self.platform = detect_platform(self.primary) if platform == "auto" else platform
        self.prs = merged_prs(self) if self.base else {}

        records = read_sessions(self.sessions_dir)
        running = [r for r in records if is_running(r, proc_root)]
        self.running_ids = {r.get("sessionId") for r in running if r.get("sessionId")}
        self.running_cwds = [(r.get("sessionId") or str(r.get("pid")), r["cwd"]) for r in running
                             if isinstance(r.get("cwd"), str)]

    def session_using(self, path):
        for sid, cwd in self.running_cwds:
            if inside(cwd, path):
                return sid
        return None


def first_line(text):
    lines = (text or "").strip().splitlines()
    return lines[0] if lines else ""


def default_branch(repo):
    p = git(repo, "symbolic-ref", "--quiet", "refs/remotes/origin/HEAD")
    if p.returncode == 0 and p.stdout.strip().startswith("refs/remotes/origin/"):
        return p.stdout.strip()[len("refs/remotes/origin/"):]
    for name in ("main", "master"):
        if git(repo, "rev-parse", "--verify", "--quiet", f"refs/remotes/origin/{name}").returncode == 0:
            return name
    return None


def detect_platform(repo):
    url = git(repo, "remote", "get-url", "origin").stdout.strip()
    if "://" in url:
        host = urlparse(url).hostname or ""
    else:
        host = url.split("@")[-1].split(":")[0] if ":" in url else ""
    host = host.lower()
    if "github" in host:
        return "github"
    if "gitlab" in host:
        return "gitlab"
    return None


def merged_prs(ctx):
    """Map branch name to [(PR number, head commit)] of merged PRs or MRs."""
    if ctx.platform == "github":
        cli = "gh"
        args = ["gh", "pr", "list", "--state", "merged", "--limit", "200",
                "--json", "number,headRefName,headRefOid"]
        keys = ("number", "headRefName", "headRefOid")
    elif ctx.platform == "gitlab":
        cli = "glab"
        args = ["glab", "mr", "list", "--merged", "-F", "json"]
        keys = ("iid", "source_branch", "sha")
    else:
        ctx.notes.append(SKIP_SQUASH + " (origin is not on GitHub or GitLab)")
        return {}
    if not shutil.which(cli):
        ctx.notes.append(SKIP_SQUASH + f" ({cli} is not installed)")
        return {}
    p = run(args, cwd=ctx.primary)
    try:
        data = json.loads(p.stdout or "[]") if p.returncode == 0 else None
    except ValueError:
        data = None
    if not isinstance(data, list):
        ctx.notes.append(SKIP_SQUASH + f" ({cli} failed: {first_line(p.stderr) or 'bad output'})")
        return {}
    out = {}
    for d in data:
        if isinstance(d, dict) and d.get(keys[1]):
            out.setdefault(d[keys[1]], []).append((d.get(keys[0]), d.get(keys[2])))
    return out


# ---------------------------------------------------------------- branches


def is_ancestor(repo, commit, ref):
    return git(repo, "merge-base", "--is-ancestor", commit, ref).returncode == 0


def merge_status(ctx, branch, tip):
    """Return (state, why). state is merged, reused or unmerged."""
    prs = ctx.prs.get(branch, [])
    same = next((n for n, head in prs if head == tip), None)
    pr = f", PR #{same}" if same is not None else ""
    if is_ancestor(ctx.primary, tip, ctx.base):
        return "merged", f"in {ctx.base}{pr}"
    if same is not None:
        return "merged", f"PR #{same} merged at the same tip"
    for number, head in prs:
        if head and is_ancestor(ctx.primary, head, tip):
            n = git(ctx.primary, "rev-list", "--count", tip, f"^{head}", f"^{ctx.base}").stdout.strip()
            return "reused", f"PR #{number} merged, then {n} more commits"
    p = git(ctx.primary, "cherry", ctx.base, tip)
    lines = p.stdout.split()
    if p.returncode == 0 and lines and "+" not in lines[::2]:
        return "merged", f"patch-equivalent commits in {ctx.base}"
    return "unmerged", ""


def is_protected(ctx, name):
    return name == ctx.default or any(fnmatch.fnmatchcase(name, pat) for pat in PROTECTED)


def refs(repo, prefix):
    out = git_out(repo, "for-each-ref", prefix, "--format=%(refname)%00%(objectname)")
    pairs = []
    for line in out.splitlines():
        name, _, sha = line.partition("\0")
        pairs.append((name, sha))
    return pairs


def branch_items(ctx, worktrees):
    checked_out = {w["branch"] for w in worktrees if w["branch"]}
    items = []
    for ref, tip in refs(ctx.primary, "refs/heads"):
        name = ref[len("refs/heads/"):]
        if is_protected(ctx, name) or name in checked_out:
            continue
        state, why = merge_status(ctx, name, tip)
        if state == "unmerged":
            continue
        items.append({"kind": "b", "target": name, "branch": name, "tip": tip, "why": why,
                      "cls": "safe" if state == "merged" else "risky"})
    return items


def remote_items(ctx):
    items = []
    for ref, tip in refs(ctx.primary, "refs/remotes/origin"):
        name = ref[len("refs/remotes/origin/"):]
        if name == "HEAD" or is_protected(ctx, name):
            continue
        state, why = merge_status(ctx, name, tip)
        if state == "merged":
            items.append({"kind": "r", "target": name, "branch": name, "tip": tip, "why": why, "cls": "safe"})
    return items


# ---------------------------------------------------------------- worktrees


def list_worktrees(repo):
    worktrees, cur = [], None
    for line in git_out(repo, "worktree", "list", "--porcelain").splitlines():
        if line.startswith("worktree "):
            cur = {"path": line[len("worktree "):], "head": None, "branch": None,
                   "locked": False, "bare": False}
            worktrees.append(cur)
        elif cur is None:
            continue
        elif line.startswith("HEAD "):
            cur["head"] = line[len("HEAD "):]
        elif line.startswith("branch refs/heads/"):
            cur["branch"] = line[len("branch refs/heads/"):]
        elif line.startswith("locked"):
            cur["locked"] = True
        elif line == "bare":
            cur["bare"] = True
    return worktrees


def same_as_primary(ctx, wt_path, rel):
    a, b = os.path.join(wt_path, rel), os.path.join(ctx.primary, rel)
    if os.path.islink(a) or os.path.islink(b):
        return os.path.islink(a) and os.path.islink(b) and os.readlink(a) == os.readlink(b)
    try:
        return os.path.isfile(b) and filecmp.cmp(a, b, shallow=False)
    except OSError:
        return False


def ignored_differences(ctx, wt_path):
    """Ignored files in the worktree that the primary checkout does not hold identically."""
    p = git(wt_path, "ls-files", "--others", "--ignored", "--exclude-standard", "--directory", "-z")
    if p.returncode != 0:
        return ["(git ls-files failed)"]
    diffs = []
    for rel in filter(None, p.stdout.split("\0")):
        rel = rel.rstrip("/")
        if any(part in BUILD_DIRS for part in rel.split("/")):
            continue
        full = os.path.join(wt_path, rel)
        if os.path.isdir(full) and not os.path.islink(full):
            for dirpath, dirnames, filenames in os.walk(full):
                dirnames[:] = [d for d in dirnames if d not in BUILD_DIRS]
                for f in filenames:
                    sub = os.path.relpath(os.path.join(dirpath, f), wt_path)
                    if not same_as_primary(ctx, wt_path, sub):
                        diffs.append(sub)
        elif not same_as_primary(ctx, wt_path, rel):
            diffs.append(rel)
    return diffs


def classify_worktree(ctx, wt):
    """Return an item, or None when the worktree is not a candidate. Kept reasons go to ctx.kept."""
    path = os.path.realpath(wt["path"]) if os.path.exists(wt["path"]) else wt["path"]
    if wt["bare"] or path in ctx.protected_paths:
        if path == ctx.current and path != ctx.primary:
            ctx.kept.append(f"{path}: current worktree")
        return None
    if wt["locked"]:
        ctx.kept.append(f"{path}: locked")
        return None
    if not os.path.isdir(path):
        return {"kind": "w", "target": path, "path": path, "dangling": True, "branch": None,
                "tip": wt["head"], "why": "folder is gone, prune the git record", "cls": "safe"}
    sid = ctx.session_using(path)
    if sid:
        ctx.kept.append(f"{path}: in use by session {sid}")
        return None
    branch, head = wt["branch"], wt["head"]
    if branch:
        state, why = merge_status(ctx, branch, head)
        if state == "unmerged":
            return None
    elif head and is_ancestor(ctx.primary, head, ctx.base):
        state, why = "merged", f"detached at a commit in {ctx.base}"
    else:
        return None
    risks = []
    if state == "reused":
        risks.append("branch has commits after the merged PR")
    st = git(path, "status", "--porcelain", "--untracked-files=all")
    dirty = [line[3:] for line in st.stdout.splitlines()] if st.returncode == 0 else ["(git status failed)"]
    if dirty:
        risks.append(f"{len(dirty)} changed or untracked files: {capped(dirty)}")
    ignored = ignored_differences(ctx, path)
    if ignored:
        risks.append(f"ignored files not in the primary checkout: {capped(ignored)}")
    primary_branch = next((w["branch"] for w in list_worktrees(ctx.primary)[:1]), None)
    delete_branch = branch if branch and not is_protected(ctx, branch) and branch != primary_branch else None
    return {"kind": "w", "target": path, "path": path, "dangling": False, "branch": delete_branch,
            "tip": head, "why": "; ".join([why] + risks), "cls": "risky" if risks else "safe",
            "dirty": len(dirty)}


def worktree_items(ctx, worktrees):
    items = []
    for wt in worktrees[1:]:
        item = classify_worktree(ctx, wt)
        if item:
            items.append(item)
    return items


def orphan_state(ctx, folder):
    """orphan when .git is a file pointing at a missing <common dir>/worktrees/<name>."""
    gitfile = os.path.join(folder, ".git")
    if os.path.islink(gitfile) or not os.path.isfile(gitfile):
        return "unknown"
    try:
        with open(gitfile, encoding="utf-8") as f:
            line = f.readline().strip()
    except OSError:
        return "unknown"
    if not line.startswith("gitdir:"):
        return "unknown"
    target = line[len("gitdir:"):].strip()
    target = os.path.realpath(os.path.join(folder, target))
    admin = os.path.join(ctx.common_dir, "worktrees")
    if os.path.dirname(target) == admin and not os.path.exists(target):
        return "orphan"
    return "unknown"


def orphan_parents(ctx):
    parent, name = os.path.dirname(ctx.primary), os.path.basename(ctx.primary)
    return os.path.join(parent, name + ".worktrees"), parent, name


def is_orphan_location(ctx, path):
    wdir, parent, name = orphan_parents(ctx)
    path = os.path.realpath(path)
    if os.path.dirname(path) == os.path.realpath(wdir):
        return True
    return os.path.dirname(path) == os.path.realpath(parent) and os.path.basename(path).startswith(name + "-")


def orphan_items(ctx, worktrees):
    wdir, parent, name = orphan_parents(ctx)
    registered = {os.path.realpath(w["path"]) for w in worktrees}
    folders = []
    if os.path.isdir(wdir):
        folders += [os.path.join(wdir, c) for c in sorted(os.listdir(wdir))]
    folders += [os.path.join(parent, c) for c in sorted(os.listdir(parent)) if c.startswith(name + "-")]
    items = []
    for folder in folders:
        if os.path.islink(folder) or not os.path.isdir(folder) or os.path.realpath(folder) in registered:
            continue
        if orphan_state(ctx, folder) == "orphan":
            items.append({"kind": "o", "target": folder, "path": folder, "cls": "risky",
                          "why": "git no longer knows this worktree, changes cannot be checked"})
        else:
            ctx.unknown.append(folder)
    return items


# ---------------------------------------------------------------- scratch folders


def encodes_subfolder(folder, rest, depth=0):
    """True when rest is the encoding of a folder that exists below folder."""
    if depth > 30:
        return False
    try:
        entries = list(os.scandir(folder))
    except OSError:
        return False
    for e in entries:
        if not e.is_dir(follow_symlinks=False):
            continue
        enc = encode(e.name)
        if rest == enc:
            return True
        if rest.startswith(enc + "-") and encodes_subfolder(e.path, rest[len(enc) + 1:], depth + 1):
            return True
    return False


def in_scope(name, paths):
    for base in paths:
        enc = encode(base)
        if name == enc:
            return True
        if name.startswith(enc + "-") and encodes_subfolder(base, name[len(enc) + 1:]):
            return True
    return False


def project_folders(ctx, scope_paths):
    try:
        names = sorted(os.listdir(ctx.scratch_root))
    except OSError:
        return []
    out = []
    for name in names:
        path = os.path.join(ctx.scratch_root, name)
        if not name.startswith("-") or os.path.islink(path) or not os.path.isdir(path):
            continue
        if ctx.all_projects or in_scope(name, scope_paths):
            out.append(path)
    return out


def inspect_folder(path):
    """Return (newest mtime of anything inside, [(rel path, size, mtime)] of content files).

    Content is every entry that is not a directory, except the top-level started marker.
    Symlinks count as content and are never followed.
    """
    newest, files, errors = None, [], []
    for dirpath, dirnames, filenames in os.walk(path, onerror=errors.append, followlinks=False):
        for name in dirnames + filenames:
            full = os.path.join(dirpath, name)
            try:
                st = os.lstat(full)
            except OSError:
                continue
            newest = st.st_mtime if newest is None else max(newest, st.st_mtime)
            if stat.S_ISDIR(st.st_mode):
                continue
            rel = os.path.relpath(full, path)
            if rel != "started":
                files.append((rel, st.st_size, st.st_mtime))
    if errors:
        files.append(("(unreadable folder)", 0, 0))
    if newest is None:
        newest = os.lstat(path).st_mtime
    return newest, files


def check_session_path(ctx, path):
    """Return None when path is <scratch root>/<project>/<session>, else the reason to refuse."""
    if os.path.islink(path):
        return "is a symlink"
    real = os.path.realpath(path)
    root = ctx.scratch_root
    if not real.startswith(root + os.sep):
        return f"resolves outside the scratch root {root}"
    parts = os.path.relpath(real, root).split(os.sep)
    if len(parts) != 2 or not parts[0].startswith("-") or not SESSION_RE.match(parts[1]):
        return "is not a <project>/<session> folder"
    return None


def session_state(ctx, path):
    """Return (state, info). state is running, recent, empty or files."""
    sid = os.path.basename(path)
    if sid in ctx.running_ids or (ctx.own and inside(ctx.own, path)):
        return "running", None
    newest, files = inspect_folder(path)
    age = (ctx.now - newest) / 86400
    info = {"age_days": round(age, 1), "size": sum(f[1] for f in files), "files": len(files),
            "newest": [f[0] for f in sorted(files, key=lambda f: -f[2])[:3]]}
    if age < ctx.days:
        return "recent", info
    return ("files" if files else "empty"), info


def session_items(ctx, scope_paths):
    empty, risky = [], []
    for proj in project_folders(ctx, scope_paths):
        try:
            names = sorted(os.listdir(proj))
        except OSError:
            continue
        for name in names:
            path = os.path.join(proj, name)
            if not SESSION_RE.match(name) or os.path.islink(path) or not os.path.isdir(path):
                continue  # session folders are named by the session id, a UUID
            state, info = session_state(ctx, path)
            if state == "empty":
                empty.append(path)
            elif state == "files":
                label = f"{os.path.basename(proj)[-32:]}/{name[:8]}"
                risky.append({"kind": "s", "target": path, "path": path, "cls": "risky", "label": label,
                              "age_days": info["age_days"], "size": info["size"],
                              "why": f"{info['age_days']:.0f} days, {human(info['size'])}, "
                                     f"{info['files']} files: {capped(info['newest'], 3)}"})
    risky.sort(key=lambda i: (-i["age_days"], -i["size"]))
    items = []
    if empty:
        items.append({"kind": "s", "target": f"{len(empty)} empty session folders", "paths": empty,
                      "cls": "safe", "group": True,
                      "why": f"not running, older than {ctx.days} days, no files except started"})
    return items + risky


def own_items(ctx):
    if not ctx.own or not os.path.isdir(ctx.own):
        return []
    items = []
    for name in sorted(os.listdir(ctx.own)):
        path = os.path.join(ctx.own, name)
        if os.path.islink(path) or not os.path.isdir(path) or not mktemp_shaped(name):
            continue
        if inside(ctx.cwd, path):
            continue
        _, files = inspect_folder(path)
        size = sum(f[1] for f in files)
        items.append({"kind": "m", "target": name, "path": path, "cls": "safe", "size": size,
                      "why": f"{len(files)} files, {human(size)}"})
    return items


# ---------------------------------------------------------------- scan


def collect(ctx):
    items = own_items(ctx)
    worktrees = list_worktrees(ctx.primary)
    if ctx.base:
        items += branch_items(ctx, worktrees)
        items += remote_items(ctx)
        items += worktree_items(ctx, worktrees)
    items += orphan_items(ctx, worktrees)
    scope = [ctx.primary] + [os.path.realpath(w["path"]) for w in worktrees[1:] if os.path.isdir(w["path"])]
    items += session_items(ctx, scope)
    counters = {}
    for item in items:
        counters[item["kind"]] = counters.get(item["kind"], 0) + 1
        item["id"] = f"{item['kind']}{counters[item['kind']]}"
    return items


def render(ctx, items, scan_file):
    if not items:
        extra = [n for n in ctx.notes if n.startswith(SKIP_SQUASH)]
        return ["Nothing to clean." + (f" Note: {extra[0]}." if extra else "")]
    lines = [f"Cleanup candidates in {ctx.primary} (merged means in {ctx.base or 'n/a'})"]
    shown = 0
    for kind, title in GROUPS:
        group = [i for i in items if i["kind"] == kind]
        if not group or shown >= TABLE_CAP:
            continue
        lines.append(f"{title}:")
        for item in group:
            if shown >= TABLE_CAP:
                break
            label = item.get("label") or display_target(ctx, item)
            lines.append(f"  {item['id']:<4} {item['cls']:<5}  {label}  ({item['why']})")
            shown += 1
    hidden = len(items) - shown
    for title, values in (("Kept", ctx.kept), ("Unknown, never deleted", ctx.unknown), ("Note", ctx.notes)):
        for value in values[:LIST_CAP]:
            lines.append(f"{title}: {value}")
        if len(values) > LIST_CAP:
            lines.append(f"{title}: {len(values) - LIST_CAP} more")
    safe = sum(1 for i in items if i["cls"] == "safe")
    folders = sum(len(i["paths"]) for i in items if i.get("group"))
    summary = f"Summary: {len(items)} items, {safe} safe, {len(items) - safe} risky"
    if folders:
        summary += f", {folders} empty session folders in one group"
    if hidden:
        summary += f"; {hidden} more items not shown, all in the scan file"
    lines.append(summary + f". Scan file: {scan_file}")
    return lines


def display_target(ctx, item):
    target = item["target"]
    parent = os.path.dirname(ctx.primary)
    if item["kind"] in ("w", "o") and target.startswith(parent + os.sep):
        target = os.path.relpath(target, parent)
    if item["kind"] == "w" and item.get("branch"):
        target += f" + branch {item['branch']}"
    return target


def scan(ctx):
    items = collect(ctx)
    os.makedirs(ctx.state_dir, exist_ok=True)
    scan_file = os.path.join(ctx.state_dir, "last-scan.json")
    data = {"version": 1, "created": ctx.now, "primary": ctx.primary, "current": ctx.current,
            "own": ctx.own, "scratch_root": ctx.scratch_root, "sessions_dir": ctx.sessions_dir,
            "days": ctx.days, "all_projects": ctx.all_projects, "notes": ctx.notes, "items": items}
    with open(scan_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)
    return render(ctx, items, scan_file), data


# ---------------------------------------------------------------- remove


def log(ctx, entry):
    os.makedirs(ctx.state_dir, exist_ok=True)
    entry = {"time": time.strftime("%Y-%m-%dT%H:%M:%S%z"), **entry}
    with open(os.path.join(ctx.state_dir, "cleanup.log"), "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def remove_tree(path):
    if os.path.islink(path):
        raise Error("is a symlink")
    shutil.rmtree(path)


def verify_branch(ctx, name, tip, allow_reused):
    p = git(ctx.primary, "rev-parse", "--verify", "--quiet", f"refs/heads/{name}")
    if p.returncode != 0:
        return "branch is gone"
    if p.stdout.strip() != tip:
        return "branch tip changed since the scan"
    if is_protected(ctx, name):
        return "protected branch"
    for w in list_worktrees(ctx.primary):
        if w["branch"] == name:
            return f"checked out in {w['path']}"
    state, _ = merge_status(ctx, name, tip)
    if state == "merged" or (state == "reused" and allow_reused):
        return None
    return f"no longer counts as merged ({state})"


def verify(ctx, item, allowed):
    """Return None when the item may be removed now, else the reason to skip it."""
    kind = item["kind"]
    if item["cls"] == "risky" and not allowed:
        return "risky, needs its own yes (--allow-risky)"
    if kind == "b":
        return verify_branch(ctx, item["branch"], item["tip"], allowed)
    if kind == "w":
        wt = next((w for w in list_worktrees(ctx.primary)
                   if w["path"] == item["path"] or os.path.realpath(w["path"]) == item["path"]), None)
        if not wt:
            return "no longer a registered worktree"
        kept = len(ctx.kept)
        fresh = classify_worktree(ctx, wt)
        if not fresh:
            return ctx.kept[-1] if len(ctx.kept) > kept else "no longer a candidate"
        if fresh["dangling"] != item["dangling"]:
            return "changed since the scan"
        if fresh["cls"] == "risky" and not allowed:
            return f"changed since the scan: {fresh['why']}"
        return None
    if kind == "o":
        if not is_orphan_location(ctx, item["path"]) or orphan_state(ctx, item["path"]) != "orphan":
            return "no longer an orphan worktree folder"
        return None
    if kind == "s":
        reason = check_session_path(ctx, item["path"])
        if reason:
            return reason
        state, _ = session_state(ctx, item["path"])
        if state == "empty" or (state == "files" and allowed):
            return None
        return f"changed since the scan ({state})"
    if kind == "m":
        path = item["path"]
        if not ctx.own or os.path.dirname(os.path.realpath(path)) != ctx.own:
            return "not in the session scratchpad"
        if os.path.islink(path) or not mktemp_shaped(os.path.basename(path)) or inside(ctx.cwd, path):
            return "not a removable mktemp folder"
        return None
    return f"unknown kind {kind}"


def remove(ctx, data, ids, risky_ids, apply):
    """Remove the given ids from a scan. Return output lines."""
    by_id = {i["id"]: i for i in data["items"]}
    wanted = list(dict.fromkeys(ids + risky_ids))
    missing = [i for i in wanted if i not in by_id]
    if missing:
        raise Error(f"unknown ids: {', '.join(missing)} (run scan again)")
    items = sorted((by_id[i] for i in wanted), key=lambda i: ("rmswob".index(i["kind"]), i["id"]))  # worktrees before branches
    lines, counts = [], {"removed": 0, "skipped": 0, "failed": 0}
    verb = "Removed" if apply else "Would remove"

    def done(item, target, result, detail="", **extra):
        counts[result] += 1
        word = {"removed": verb, "skipped": "Skipped", "failed": "Failed"}[result]
        if not (item.get("group") and result == "removed"):  # a group prints one summary line
            lines.append(f"{word} {item['id']} {target}" + (f": {detail}" if detail else ""))
        if apply:
            log(ctx, {"id": item["id"], "kind": item["kind"], "target": target, "result": result,
                      "detail": detail, **extra})

    remote = [i for i in items if i["kind"] == "r"]
    if remote:
        names = " ".join(i["branch"] for i in remote)
        lines.append("The script never pushes. Remote branches are deleted with one push:")
        lines.append(f"  git -C {ctx.primary} push origin --delete {names}")
        if apply:
            for i in remote:
                log(ctx, {"id": i["id"], "kind": "r", "target": i["branch"], "result": "push-command-printed",
                          "tip": i["tip"]})

    for item in (i for i in items if i["kind"] != "r"):
        allowed = item["id"] in risky_ids
        if item.get("group"):
            before = counts["removed"]
            for path in item["paths"]:
                reason = verify(ctx, dict(item, path=path, group=False), allowed)
                if reason:
                    done(item, path, "skipped", reason)
                    continue
                remove_path(item, path, apply, done)
            lines.append(f"{verb} {item['id']}: {counts['removed'] - before} of {len(item['paths'])} "
                         "empty session folders")
            continue
        reason = verify(ctx, item, allowed)
        if reason:
            done(item, item["target"], "skipped", reason, **tip_of(item))
            continue
        if item["kind"] == "b":
            remove_branch(ctx, item, item["branch"], item["tip"], apply, done)
        elif item["kind"] == "w":
            remove_worktree(ctx, item, allowed, apply, done)
        else:
            remove_path(item, item["path"], apply, done)
    lines.append(f"{'Done' if apply else 'Dry run'}: {counts['removed']} {'removed' if apply else 'to remove'}, "
                 f"{counts['skipped']} skipped, "
                 f"{counts['failed']} failed." + (f" Log: {os.path.join(ctx.state_dir, 'cleanup.log')}"
                                                   if apply else " Nothing was deleted. Add --apply to delete."))
    return lines


def tip_of(item):
    return {"tip": item["tip"]} if item.get("tip") else {}


def remove_path(item, path, apply, done):
    if not apply:
        return done(item, path, "removed")
    try:
        remove_tree(path)
    except (OSError, Error) as e:
        return done(item, path, "failed", str(e))
    done(item, path, "removed")


def remove_branch(ctx, item, name, tip, apply, done):
    if not apply:
        return done(item, f"branch {name}", "removed", f"tip {tip[:10]}", tip=tip)
    p = git(ctx.primary, "branch", "-D", name)
    if p.returncode != 0:
        return done(item, f"branch {name}", "failed", first_line(p.stderr), tip=tip)
    done(item, f"branch {name}", "removed", f"tip {tip}, restore with: git branch {name} {tip}", tip=tip)


def remove_worktree(ctx, item, allowed, apply, done):
    path = item["path"]
    if item["dangling"]:
        if apply:
            p = git(ctx.primary, "worktree", "prune")
            if p.returncode != 0:
                return done(item, path, "failed", first_line(p.stderr))
        return done(item, path, "removed", "pruned the git record")
    if apply:
        p = git(ctx.primary, "worktree", "remove", path)
        if p.returncode != 0:
            return done(item, path, "skipped", f"git refused: {first_line(p.stderr)}", **tip_of(item))
    done(item, path, "removed", **tip_of(item))
    name = item.get("branch")
    if not name:
        return
    if apply:
        reason = verify_branch(ctx, name, item["tip"], allowed)
        if reason:
            return done(item, f"branch {name}", "skipped", reason, tip=item["tip"])
    remove_branch(ctx, item, name, item["tip"], apply, done)


# ---------------------------------------------------------------- CLI


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--repo", default=".", help="any folder of the repository (default: .)")
    common.add_argument("--scratch-root", help="Claude scratch root (default: from --own, else /tmp/claude-<uid>)")
    common.add_argument("--sessions-dir", help="Claude session records (default: ~/.claude/sessions)")

    p_scan = sub.add_parser("scan", parents=[common], help="list candidates, delete nothing")
    p_scan.add_argument("--own", metavar="SCRATCHPAD", help="this session's scratchpad: list its mktemp folders")
    p_scan.add_argument("--days", type=int, default=7, help="minimum age of session folders (default: 7)")
    p_scan.add_argument("--all-projects", action="store_true", help="scan session folders of every project")

    p_rm = sub.add_parser("remove", parents=[common], help="remove ids of the last scan (dry run unless --apply)")
    p_rm.add_argument("--ids", default="", help="comma-separated ids from the scan, e.g. b1,w2,s1")
    p_rm.add_argument("--allow-risky", default="", help="comma-separated risky ids the user approved one by one")
    p_rm.add_argument("--apply", action="store_true", help="really delete")
    args = parser.parse_args(argv)

    try:
        if args.command == "scan":
            ctx = Context(args.repo, scratch_root=args.scratch_root, sessions_dir=args.sessions_dir,
                          days=args.days, all_projects=args.all_projects, own=args.own)
            lines, _ = scan(ctx)
        else:
            scan_file = os.path.join(default_state_dir(), "last-scan.json")
            try:
                with open(scan_file, encoding="utf-8") as f:
                    data = json.load(f)
            except (OSError, ValueError):
                raise Error(f"no scan found at {scan_file}, run scan first")
            ctx = Context(args.repo, scratch_root=args.scratch_root or data["scratch_root"],
                          sessions_dir=args.sessions_dir or data["sessions_dir"], days=data["days"],
                          own=data.get("own"), fetch=False)
            if ctx.primary != data["primary"]:
                raise Error(f"the last scan was for {data['primary']}, not {ctx.primary}")
            ctx.protected_paths.add(data["current"])
            split = lambda s: [x.strip() for x in s.split(",") if x.strip()]  # noqa: E731
            lines = remove(ctx, data, split(args.ids), split(args.allow_risky), args.apply)
    except Error as e:
        print(f"cleanup: {e}", file=sys.stderr)
        return 2
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())

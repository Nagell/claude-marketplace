#!/usr/bin/env python3
"""List the repo's own instruction files that apply to each changed path.

Looked for, per changed path:
  - ``CLAUDE.md``, ``.claude/CLAUDE.md``, ``AGENTS.md`` and ``.editorconfig``
    in the file's directory and every parent up to the repo root
  - root ``CONTRIBUTING.md``, ``.github/copilot-instructions.md`` and
    ``.cursorrules``
  - ``.github/instructions/*.instructions.md`` whose ``applyTo`` glob matches
  - ``.cursor/rules/**/*.mdc`` whose ``globs`` match, or with
    ``alwaysApply: true``

With ``--ref <sha>`` the files are listed and counted as they are at that
commit (``git ls-tree`` and ``git show``), not in the working tree. The review
passes ``base_sha``, so an MR cannot change which rules review it.

Prints one JSON object:
  {"ref": <sha or null>,
   "paths": {<changed path>: [{"path": ..., "lines": <int>,
                               "changed": <bool>}, ...]}}

``changed`` is true when the MR changes that instruction file itself: the
agent reads the rules at ``base_sha`` and reviews the diff as code.
"""

from __future__ import annotations

import argparse
import json
import posixpath
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

PER_DIR = ("CLAUDE.md", ".claude/CLAUDE.md", "AGENTS.md", ".editorconfig")
ROOT_ONLY = ("CONTRIBUTING.md", ".github/copilot-instructions.md", ".cursorrules")


class Tree:
    """The repo's files, either in the working tree or at a git ref."""

    def __init__(self, root: Path, ref: str | None):
        self.root = root
        self.ref = ref
        self.links: set[str] = set()
        if ref:
            # --full-tree: paths from the repo root, as `git show ref:path` reads them
            out = subprocess.run(
                ["git", "-C", str(root), "ls-tree", "-r", "-z", "--full-tree", ref],
                capture_output=True, text=True,
            )
            if out.returncode != 0:
                sys.exit(f"git ls-tree {ref} failed: {out.stderr.strip()}")
            # -z: names come raw, not quoted, so non-ASCII paths match.
            self.files = set()
            for item in filter(None, out.stdout.split("\0")):
                meta, _, name = item.partition("\t")
                self.files.add(name)
                if meta.startswith("120000"):
                    self.links.add(name)
        else:
            self.files = {
                p.relative_to(root).as_posix()
                for p in root.rglob("*")
                if p.is_file() and ".git" not in p.relative_to(root).parts
            }

    def exists(self, rel: str) -> bool:
        return rel in self.files

    def read(self, rel: str) -> str:
        if self.ref:
            out = subprocess.run(
                ["git", "-C", str(self.root), "show", f"{self.ref}:{rel}"],
                capture_output=True,
            )
            if out.returncode != 0:
                sys.exit(f"git show {self.ref}:{rel} failed: "
                         f"{out.stderr.decode('utf-8', 'replace').strip()}")
            text = out.stdout.decode("utf-8", "replace")
            if rel in self.links:  # a symlink blob holds the target name: read the target
                target = posixpath.normpath(posixpath.join(posixpath.dirname(rel), text.strip()))
                if target in self.files and target not in self.links:
                    return self.read(target)
            return text
        return (self.root / rel).read_text(encoding="utf-8", errors="replace")

    def lines(self, rel: str) -> int:
        return len(self.read(rel).splitlines())

    def under(self, prefix: str, suffix: str) -> list[str]:
        return sorted(f for f in self.files
                      if f.startswith(prefix) and f.endswith(suffix))


def glob_to_regex(pattern: str) -> re.Pattern:
    """Translate a ``**``-style glob to a regex over a repo-relative path."""
    pattern = pattern.strip().lstrip("/")
    if pattern.startswith("./"):
        pattern = pattern[2:]
    out, i = "", 0
    while i < len(pattern):
        c = pattern[i]
        if pattern.startswith("**/", i):
            out += "(?:.*/)?"
            i += 3
        elif pattern.startswith("**", i):
            out += ".*"
            i += 2
        elif c == "*":
            out += "[^/]*"
            i += 1
        elif c == "?":
            out += "[^/]"
            i += 1
        elif c == "{":
            end = pattern.find("}", i)
            if end == -1:
                out += re.escape(c)
                i += 1
            else:
                alts = pattern[i + 1:end].split(",")
                out += "(?:" + "|".join(re.escape(a) for a in alts) + ")"
                i = end + 1
        else:
            out += re.escape(c)
            i += 1
    return re.compile(out + r"\Z")


def glob_match(pattern: str, path: str) -> bool:
    """A pattern with no ``/`` matches the file name at any depth."""
    if not pattern.strip():
        return False
    rx = glob_to_regex(pattern)
    if rx.match(path):
        return True
    return "/" not in pattern.strip() and bool(rx.match(PurePosixPath(path).name))


def frontmatter(text: str) -> dict[str, str]:
    """Top-level ``key: value`` pairs of a ``---`` block; lists joined by ``,``."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    data: dict[str, str] = {}
    key = None
    for line in lines[1:]:
        if line.strip() == "---":
            break
        item = re.match(r"\s+-\s+(.+)$", line)
        if item and key:
            data[key] = ",".join(filter(None, [data[key], item.group(1)]))
            continue
        m = re.match(r"([A-Za-z_][\w-]*)\s*:\s*(.*)$", line)
        if m:
            key = m.group(1)
            data[key] = m.group(2).strip()
    return data


def split_globs(value: str) -> list[str]:
    """Split on commas outside ``{...}``, so ``*.{ts,tsx}`` stays one glob."""
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        value = value[1:-1]
    parts, cur, depth = [], "", 0
    for c in value:
        if c == "{":
            depth += 1
        elif c == "}":
            depth = max(depth - 1, 0)
        if c == "," and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += c
    parts.append(cur)
    return [g.strip().strip("'\"") for g in parts if g.strip().strip("'\"")]


def scoped_files(tree: Tree) -> list[tuple[str, list[str] | None]]:
    """(file, globs) for scoped rule files; ``None`` globs means always apply."""
    found: list[tuple[str, list[str] | None]] = []
    for f in tree.under(".github/instructions/", ".instructions.md"):
        globs = split_globs(frontmatter(tree.read(f)).get("applyTo", ""))
        found.append((f, globs))
    for f in tree.under(".cursor/rules/", ".mdc"):
        fm = frontmatter(tree.read(f))
        if fm.get("alwaysApply", "").strip().lower() == "true":
            found.append((f, None))
        else:
            found.append((f, split_globs(fm.get("globs", ""))))
    return found


def lookup(paths: list[str], root: Path, ref: str | None) -> dict:
    tree = Tree(root, ref)
    changed = set(paths)
    scoped = scoped_files(tree)
    counts: dict[str, int] = {}

    def entry(rel: str) -> dict:
        if rel not in counts:
            counts[rel] = tree.lines(rel)
        return {"path": rel, "lines": counts[rel], "changed": rel in changed}

    result: dict[str, list[dict]] = {}
    for p in paths:
        hits: list[str] = []
        parent = PurePosixPath(p).parent
        dirs = [parent, *parent.parents]
        for d in reversed(dirs):  # root first
            for name in PER_DIR:
                rel = name if str(d) == "." else f"{d.as_posix()}/{name}"
                if tree.exists(rel):
                    hits.append(rel)
        hits += [r for r in ROOT_ONLY if tree.exists(r)]
        for f, globs in scoped:
            if globs is None or any(glob_match(g, p) for g in globs):
                hits.append(f)
        result[p] = [entry(h) for h in dict.fromkeys(hits)]
    return {"ref": ref, "paths": result}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*", help="changed paths, relative to the repo root")
    ap.add_argument("--repo", default=".", help="repo root (default: cwd)")
    ap.add_argument("--ref", default=None,
                    help="read instruction files at this commit (pass base_sha)")
    ap.add_argument("--paths-file", default=None,
                    help="read changed paths from this file, one per line ('-' for stdin)")
    a = ap.parse_args()
    paths = list(a.paths)
    if a.paths_file:
        fh = sys.stdin if a.paths_file == "-" else open(a.paths_file, encoding="utf-8")
        paths += [line.strip() for line in fh if line.strip()]
    print(json.dumps(lookup(paths, Path(a.repo).resolve(), a.ref), indent=2))


if __name__ == "__main__":
    main()

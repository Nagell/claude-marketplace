#!/usr/bin/env python3
"""Find the project rules file for the repo under review.

The repo name comes from ``git remote get-url origin``, not from the directory
name, because a worktree's directory is named after the worktree. The rules
folder is ``~/.claude/review-rules`` (``REVIEW_RULES_DIR`` overrides it).

Lookup order:
  1. ``<rules dir>/<repo name>.md``
  2. the first file (by name) whose frontmatter ``applies-to:`` list holds the
     repo name. Only the frontmatter is read, up to its closing ``---``.

Prints one JSON object:
  {"repo": ..., "path": <file or null>, "expected": <rules dir>/<repo>.md,
   "matched_by": "name" | "applies-to" | null, "skipped": [...],
   "counterpart": <bool>, "declined": <bool>}

``declined`` is true when the repo is listed in ``<rules dir>/.declined``, one
name per line: the user said no to creating a rules file for it. An unreadable
``.declined`` is listed in ``skipped``. ``--decline`` adds the repo to that
list first (creating the folder and the file when missing).

``skipped`` lists files whose frontmatter could not be read, with the reason,
so a typo in a rules file does not read like "no rules for this repo". A file
with no frontmatter at all is a rules file found by its name only, so the
``applies-to`` scan passes over it without reporting it.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

DEFAULT_DIR = "~/.claude/review-rules"


def rules_dir() -> Path:
    return Path(os.environ.get("REVIEW_RULES_DIR") or DEFAULT_DIR).expanduser()


def repo_name_from_url(url: str) -> str:
    """Last path segment of a git remote URL, without ``.git``.

    Handles ``git@host:group/sub/repo.git``, ``https://host/group/repo`` and
    local paths alike.
    """
    tail = re.split(r"[/:]", url.strip().rstrip("/"))[-1]
    return tail[:-4] if tail.endswith(".git") else tail


def repo_name_from_git(repo_dir: str) -> str:
    proc = subprocess.run(
        ["git", "-C", repo_dir, "remote", "get-url", "origin"],
        capture_output=True, text=True,
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        sys.exit(
            f"no origin remote in {repo_dir}: {proc.stderr.strip() or 'empty url'}. "
            "Run this inside the repo under review, or pass --repo-name."
        )
    return repo_name_from_url(proc.stdout)


class FrontmatterError(ValueError):
    pass


class NoFrontmatter(FrontmatterError):
    pass


def read_frontmatter(path: Path) -> list[str]:
    """Lines between the opening and closing ``---``; the body is never read."""
    with path.open(encoding="utf-8-sig") as fh:
        first = fh.readline()
        if first.strip() != "---":
            raise NoFrontmatter("no frontmatter (first line is not ---)")
        lines = []
        for line in fh:
            if line.strip() == "---":
                return lines
            lines.append(line.rstrip("\n"))
    raise FrontmatterError("frontmatter is never closed with ---")


def applies_to(lines: list[str]) -> list[str]:
    """The ``applies-to`` list, in flow (``[a, b]``) or block (``- a``) form."""
    for i, line in enumerate(lines):
        m = re.match(r"applies-to:\s*(.*)$", line)
        if not m:
            continue
        value = m.group(1).strip()
        if value.startswith("["):
            if not value.endswith("]"):
                raise FrontmatterError("applies-to: flow list is not closed with ]")
            return [_scalar(v) for v in value[1:-1].split(",") if v.strip()]
        return [_scalar(value)] if value else _block_list(lines[i + 1:])
    return []


def _block_list(lines: list[str]) -> list[str]:
    items = []
    for line in lines:
        item = re.match(r"\s*-\s+(.+)$", line)
        if not item:
            break
        items.append(_scalar(item.group(1)))
    if not items:
        raise FrontmatterError("applies-to: is empty")
    return items


def _scalar(v: str) -> str:
    return v.strip().strip("'\"")


_HEADING = re.compile(r"^ {0,3}##[ \t]+Counterpart[ \t]*(#+[ \t]*)?$")
_FENCE = re.compile(r"^ {0,3}(```|~~~)")


def has_counterpart(path: Path) -> bool:
    """True when the rules file has a `## Counterpart` heading.

    A heading inside a code fence or an HTML comment does not count. A file
    that cannot be read counts as none; a byte that is not UTF-8 does not stop
    the read.
    """
    try:
        text = path.read_bytes().decode("utf-8-sig", "replace")
    except OSError:
        return False
    fence = None
    comment = False
    for line in text.splitlines():
        if comment:
            # the line holding the closing marker still belongs to the comment
            # block, as in Markdown, so nothing on it can be a heading
            if "-->" in line:
                comment = False
            continue
        m = _FENCE.match(line)
        if m:
            fence = None if fence == m.group(1) else (fence or m.group(1))
            continue
        if fence is not None:
            continue
        line = re.sub(r"<!--.*?-->", "", line)
        if "<!--" in line:
            comment, line = True, line.split("<!--", 1)[0]
        if _HEADING.match(line):
            return True
    return False


def is_declined(repo: str, folder: Path) -> bool:
    """True when ``<folder>/.declined`` lists the repo on a line of its own.

    A missing file means nothing is declined. Any other read error raises
    ``OSError``, so the caller can report it instead of offering again.
    """
    try:
        text = (folder / ".declined").read_bytes().decode("utf-8-sig", "replace")
    except FileNotFoundError:
        return False
    return repo in {line.strip() for line in text.splitlines()}


def decline(repo: str, folder: Path) -> None:
    """Add the repo to ``<folder>/.declined``, creating both when missing."""
    if is_declined(repo, folder):
        return
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / ".declined"
    lead = ""
    if path.exists() and path.stat().st_size:
        with path.open("rb") as fh:
            fh.seek(-1, os.SEEK_END)
            lead = "" if fh.read(1) == b"\n" else "\n"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(f"{lead}{repo}\n")


def find(repo: str, folder: Path) -> dict:
    expected = folder / f"{repo}.md"
    result = {"repo": repo, "path": None, "expected": str(expected),
              "matched_by": None, "skipped": []}
    if expected.is_file():
        result.update(path=str(expected), matched_by="name")
        return result
    if not folder.is_dir():
        return result
    for f in sorted(folder.glob("*.md")):
        try:
            names = applies_to(read_frontmatter(f))
        except NoFrontmatter:
            continue
        except (FrontmatterError, UnicodeDecodeError, OSError) as e:
            result["skipped"].append({"path": str(f), "reason": str(e)})
            continue
        if repo in names:
            result.update(path=str(f), matched_by="applies-to")
            return result
    return result


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--repo-dir", default=".", help="a checkout of the repo (default: cwd)")
    p.add_argument("--repo-name", default=None,
                   help="use this name instead of reading the origin remote, "
                        "e.g. the last segment of the MR's project path")
    p.add_argument("--decline", action="store_true",
                   help="add the repo to <rules dir>/.declined, then print as usual")
    a = p.parse_args()
    repo = a.repo_name or repo_name_from_git(a.repo_dir)
    if a.decline:
        decline(repo, rules_dir())
    result = find(repo, rules_dir())
    result["counterpart"] = bool(result["path"]) and has_counterpart(Path(result["path"]))
    try:
        result["declined"] = is_declined(repo, rules_dir())
    except OSError as e:
        result["declined"] = False
        result["skipped"].append({"path": str(rules_dir() / ".declined"), "reason": str(e)})
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

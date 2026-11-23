#!/usr/bin/env python3
"""Find which apps in a repo render on the server, from their framework configs.

Each framework in ``FRAMEWORKS`` names its config files and the setting that
turns server rendering off. A config that sets it off renders client-only; a
config that computes the value (an environment variable, a function call) is
``"unknown"``, which the review treats as rendering on the server; a config
without the setting uses the framework default, server rendering.

The configs are read as text, not evaluated. Line comments are ignored, so a
comment that mentions ``ssr: false`` decides nothing.

With ``--ref <sha>`` the files are listed and read as they are at that commit.
The review passes ``head_sha``: the MR may itself switch rendering on or off.

Prints one JSON object:
  {"ref": <sha or null>,
   "apps": [{"root": <dir, "" for the repo root>, "framework": <name>,
             "config": <path>, "renders_on_server": true | false | "unknown",
             "evidence": <"path:line: text" or the default it fell back to>}]}
"""

from __future__ import annotations

import argparse
import json
import posixpath
import re
import subprocess
import sys
from pathlib import Path

FRAMEWORKS = (
    {
        "name": "nuxt",
        "config": re.compile(r"(^|/)nuxt\.config\.(ts|mts|js|mjs|cjs)$"),
        "setting": re.compile(r"\bssr\s*:\s*(.+?)\s*,?\s*$"),
        "off": re.compile(r"^false$"),
        "on": re.compile(r"^true$"),
        "default": "no `ssr` setting: Nuxt renders on the server by default",
    },
    {
        "name": "next",
        "config": re.compile(r"(^|/)next\.config\.(ts|mts|js|mjs|cjs)$"),
        "setting": re.compile(r"\boutput\s*:\s*(.+?)\s*,?\s*$"),
        "off": re.compile(r"""^['"]export['"]$"""),
        "on": re.compile(r"""^['"](standalone|server)['"]$"""),
        "default": "no `output: 'export'`: Next.js renders on the server by default",
    },
)

SKIP_PARTS = {"node_modules", ".nuxt", ".output", ".next", "dist"}
LINE_COMMENT = re.compile(r"(^|\s)//.*$")


def list_files(repo: Path, ref: str | None) -> list[str]:
    cmd = ["git", "-C", str(repo), "ls-tree", "-r", "-z", "--name-only", "--full-tree", ref] \
        if ref else ["git", "-C", str(repo), "ls-files", "-z"]
    out = subprocess.run(cmd, capture_output=True, text=True)
    if out.returncode != 0:
        sys.exit(f"{' '.join(cmd[3:5])} failed: {out.stderr.strip()}")
    return [name for name in out.stdout.split("\0") if name]


def read_file(repo: Path, ref: str | None, rel: str) -> str:
    if not ref:
        return (repo / rel).read_text(encoding="utf-8", errors="replace")
    out = subprocess.run(["git", "-C", str(repo), "show", f"{ref}:{rel}"], capture_output=True)
    if out.returncode != 0:
        sys.exit(f"git show {ref}:{rel} failed: {out.stderr.decode('utf-8', 'replace').strip()}")
    return out.stdout.decode("utf-8", "replace")


def decide(framework: dict, path: str, text: str) -> tuple[bool | str, str]:
    for number, raw in enumerate(text.splitlines(), start=1):
        line = LINE_COMMENT.sub("", raw).strip()
        if line.startswith("*") or line.startswith("/*"):
            continue
        match = framework["setting"].search(line)
        if not match:
            continue
        value = match.group(1)
        evidence = f"{path}:{number}: {raw.strip()}"
        if framework["off"].match(value):
            return False, evidence
        if framework["on"].match(value):
            return True, evidence
        return "unknown", evidence
    return True, framework["default"]


def find(repo: Path, ref: str | None) -> dict:
    apps = []
    for path in sorted(list_files(repo, ref)):
        if SKIP_PARTS.intersection(path.split("/")):
            continue
        for framework in FRAMEWORKS:
            if framework["config"].search(path):
                renders, evidence = decide(framework, path, read_file(repo, ref, path))
                apps.append({
                    "root": posixpath.dirname(path),
                    "framework": framework["name"],
                    "config": path,
                    "renders_on_server": renders,
                    "evidence": evidence,
                })
    return {"ref": ref, "apps": apps}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--ref", help="read the configs at this commit")
    args = parser.parse_args()
    print(json.dumps(find(args.repo, args.ref), indent=2))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Find which apps in a repo render on the server, from their framework configs.

Each framework in ``FRAMEWORKS`` names its config files and the setting that
turns server rendering off, if it has one (Next.js has none: a static export
still renders HTML at build time). A config that sets it off renders client-only; a
config that computes the value (an environment variable, a function call) is
``"unknown"``, which the review treats as rendering on the server; a config
without the setting uses the framework default, server rendering.

The configs are read as text, not evaluated. Comments are ignored, so a
comment that mentions ``ssr: false`` decides nothing. Only a setting at the top
level of the config object counts: ``ssr: false`` inside ``routeRules`` or
``$production`` switches rendering for some routes or builds only, so a config
with only nested settings is ``"unknown"``, and so is one that sets the value
twice at the top level.

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
        "setting": re.compile(r"(?<![\w$.])ssr\s*:\s*([^,}\n]+?)\s*(?=,|}|$)", re.M),
        "off": re.compile(r"^false$"),
        "on": re.compile(r"^true$"),
        "default": "no `ssr` setting: Nuxt renders on the server by default",
    },
    {
        "name": "next",
        "config": re.compile(r"(^|/)next\.config\.(ts|mts|js|mjs|cjs)$"),
        "setting": re.compile(r"(?<![\w$.])output\s*:\s*([^,}\n]+?)\s*(?=,|}|$)", re.M),
        # a static export still renders every page to HTML, at build time, so
        # hydration mismatches and browser globals during render still apply
        "off": re.compile(r"(?!)"),
        "on": re.compile(r"""^['"](export|standalone|server)['"]$"""),
        "default": "no `output` setting: Next.js renders on the server by default",
    },
)

SKIP_PARTS = {"node_modules", ".nuxt", ".output", ".next", "dist"}


def list_files(repo: Path, ref: str | None) -> list[str]:
    cmd = ["git", "-C", str(repo), "ls-tree", "-r", "-z", "--name-only", "--full-tree", ref] \
        if ref else ["git", "-C", str(repo), "ls-files", "-z"]
    out = subprocess.run(cmd, capture_output=True)
    if out.returncode != 0:
        err = out.stderr.decode("utf-8", "replace").strip()
        sys.exit(f"{' '.join(cmd[3:5])} failed: {err}")
    return [name for name in out.stdout.decode("utf-8", "replace").split("\0") if name]


def read_file(repo: Path, ref: str | None, rel: str) -> str:
    if not ref:
        return (repo / rel).read_text(encoding="utf-8", errors="replace")
    out = subprocess.run(["git", "-C", str(repo), "show", f"{ref}:{rel}"], capture_output=True)
    if out.returncode != 0:
        sys.exit(f"git show {ref}:{rel} failed: {out.stderr.decode('utf-8', 'replace').strip()}")
    return out.stdout.decode("utf-8", "replace")


def scan(text: str) -> tuple[str, list[int]]:
    """Blank out comments and give the brace depth at each character.

    String contents are masked too, so neither a brace nor a setting inside a
    string counts. Lengths are kept, so a position in the result is the same
    position in ``text``, where a value such as ``'export'`` is read from.
    """
    out, depth, level = [], [], 0
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if text.startswith("//", i) and (i == 0 or text[i - 1] != ":"):
            j = text.find("\n", i)
            j = n if j < 0 else j
            out.append(" " * (j - i)); depth.extend([level] * (j - i)); i = j
        elif text.startswith("/*", i):
            j = text.find("*/", i + 2)
            j = n if j < 0 else j + 2
            out.append(re.sub(r"[^\n]", " ", text[i:j])); depth.extend([level] * (j - i)); i = j
        elif c in "'\"`":
            j = i + 1
            while j < n and text[j] != c and not (c != "`" and text[j] == "\n"):
                j += 2 if text[j] == "\\" else 1
            j = min(j + 1, n)
            out.append(c + re.sub(r"[^\n]", "\0", text[i + 1:j - 1]) + text[j - 1:j] if j - i > 1 else c)
            depth.extend([level] * (j - i)); i = j
        else:
            if c == "}":
                level -= 1
            out.append(c); depth.append(level)
            if c == "{":
                level += 1
            i += 1
    return "".join(out), depth


def decide(framework: dict, path: str, text: str) -> tuple[bool | str, str]:
    code, depth = scan(text)
    top, nested = [], []
    for match in framework["setting"].finditer(code):
        number = code.count("\n", 0, match.start()) + 1
        evidence = f"{path}:{number}: {text.splitlines()[number - 1].strip()}"
        value = text[match.start(1):match.end(1)]
        (top if depth[match.start()] == 1 else nested).append((value, evidence))
    if len(top) == 1:
        value, evidence = top[0]
        if framework["off"].match(value):
            return False, evidence
        if framework["on"].match(value):
            return True, evidence
        return "unknown", evidence
    if top:
        return "unknown", f"set {len(top)} times at the top level: " + "; ".join(e for _, e in top)
    if nested:
        return "unknown", "only nested settings, which switch some routes or builds: " + nested[0][1]
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

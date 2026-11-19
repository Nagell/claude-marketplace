#!/usr/bin/env python3
"""Update the Herdr app mods setup-zsh installs, in one command.

Pulls each source repo in ~/.local/src (cloning it when missing) and copies each mod
folder into ~/.config/herdr-app/mods (or $HERDR_APP_HOME/mods). Only mods that are
already installed are updated; `--install NAME...` adds others from the table.

For each mod that changed:
- the old folder is kept in ~/.cache/herdr-mods-backup/<name>-<version>-<time>
- the installed mod.json is kept, since it holds the person's settings: only `version`
  and keys the new mod.json adds are taken from the new one
- `herdr-app check` runs on the result

`--dry-run` pulls nothing and changes nothing: it says what would change.
"""
import filecmp
import fnmatch
import json
import os
import shutil
import subprocess
import sys
import time

SRC = os.path.expanduser("~/.local/src")
# Files Herdr writes into every installed mod (editor types, caches): never compared,
# and kept across an update.
HERDR_OWNED = ("gpui-kit.d.ts", "jsconfig.json", ".cache*", "__pycache__")
BACKUPS = os.path.expanduser("~/.cache/herdr-mods-backup")

# repo folder, clone URL, {mod name: path in the repo}
REPOS = [
    ("herdr-mods", "https://github.com/munza/herdr-mods", {
        "better-files": "better-files/mods/better-files",
        "better-icons": "better-icons/mods/better-icons",
        "better-changes": "better-changes/mods/better-changes",
    }),
    ("herdr-git-graph", "https://github.com/Nagell/herdr-git-graph", {
        "git-graph": "mods/git-graph",
    }),
    ("herdr-nested-tabs", "https://github.com/Nagell/herdr-nested-tabs", {
        "nested-tabs": "mods/nested-tabs",
        "tabs-bar": "mods/tabs-bar",
    }),
    ("herdr-over9k", "https://github.com/herunan/herdr-over9k", {
        "over9k-prompts": "over9k-timeline/mods/over9k-prompts",
        "over9k-usage": "over9k-usage/mods/over9k-usage",
    }),
]


def mods_dir():
    app = os.environ.get("HERDR_APP_HOME") or os.path.expanduser("~/.config/herdr-app")
    return os.path.join(app, "mods")


def read_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def merged_manifest(old, new):
    """The installed mod.json with the new version and any keys the new one adds."""
    if not isinstance(old, dict):
        return new
    if not isinstance(new, dict):
        return old
    out = dict(old)
    for key, value in new.items():
        if key == "version" or key not in out:
            out[key] = value
    return out


def same_tree(a, b):
    """Whether two folders hold the same files with the same contents, Herdr's own aside."""
    cmp = filecmp.dircmp(a, b, ignore=list(_owned_names(a)) + list(_owned_names(b)))
    if cmp.left_only or cmp.right_only or cmp.funny_files:
        return False
    _, mismatch, errors = filecmp.cmpfiles(a, b, cmp.common_files, shallow=False)
    if mismatch or errors:
        return False
    return all(same_tree(os.path.join(a, d), os.path.join(b, d)) for d in cmp.common_dirs)


def _owned_names(folder):
    """The names in folder that Herdr owns."""
    try:
        names = os.listdir(folder)
    except OSError:
        return []
    return [n for n in names if any(fnmatch.fnmatch(n, p) for p in HERDR_OWNED)]


def _keep_owned(old, new):
    """Copy Herdr's own files from the old folder into the new one, at every depth."""
    for dirpath, dirnames, _ in os.walk(old):
        rel = os.path.relpath(dirpath, old)
        for name in _owned_names(dirpath):
            src = os.path.join(dirpath, name)
            dst = os.path.join(new, rel, name)
            if os.path.exists(dst) or not os.path.isdir(os.path.join(new, rel)):
                continue
            if os.path.isdir(src):
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)
        dirnames[:] = [d for d in dirnames if d not in _owned_names(dirpath)]


def changes(installed, source):
    """Whether installing source over installed would change anything, mod.json merged."""
    if not os.path.isdir(installed):
        return True
    old = read_json(os.path.join(installed, "mod.json"))
    new = read_json(os.path.join(source, "mod.json"))
    if merged_manifest(old, new) != old:
        return True
    # Compare against the new files with the installed mod.json in place, since that's
    # what an install would leave.
    tmp = os.path.join(BACKUPS, ".compare")
    shutil.rmtree(tmp, ignore_errors=True)
    shutil.copytree(source, tmp, ignore=shutil.ignore_patterns("mod.json", *HERDR_OWNED))
    if os.path.exists(os.path.join(installed, "mod.json")):
        shutil.copy2(os.path.join(installed, "mod.json"), os.path.join(tmp, "mod.json"))
    try:
        return not same_tree(installed, tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def git(args, cwd=None):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


def pull(folder, url):
    """Pull the repo, or clone it when missing. Returns an error message or None."""
    path = os.path.join(SRC, folder)
    if os.path.isdir(os.path.join(path, ".git")):
        r = git(["-C", path, "pull", "-q", "--ff-only"])
    else:
        os.makedirs(SRC, exist_ok=True)
        r = git(["clone", "-q", "--depth", "1", url, path])
    return None if r.returncode == 0 else (r.stderr.strip() or f"git exited {r.returncode}")


def install(name, source, target):
    """Back up target, copy source over it keeping the installed mod.json's settings."""
    old = read_json(os.path.join(target, "mod.json"))
    backup = None
    if os.path.isdir(target):
        version = (old or {}).get("version", "unversioned")
        backup = os.path.join(BACKUPS, f"{name}-{version}-{time.strftime('%Y%m%d-%H%M%S')}")
        os.makedirs(BACKUPS, exist_ok=True)
        shutil.move(target, backup)
    shutil.copytree(source, target, ignore=shutil.ignore_patterns(*HERDR_OWNED))
    if backup:
        _keep_owned(backup, target)
    new = read_json(os.path.join(target, "mod.json"))
    manifest = merged_manifest(old, new)
    if manifest is not None and manifest != new:
        with open(os.path.join(target, "mod.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
            f.write("\n")
    return backup


def check(target):
    try:
        r = subprocess.run(["herdr-app", "check", target], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as e:
        return f"herdr-app check didn't run: {e}"
    return None if r.returncode == 0 else (r.stdout + r.stderr).strip()


def main(argv):
    dry = "--dry-run" in argv
    wanted = set()
    if "--install" in argv:
        wanted = {a for a in argv[argv.index("--install") + 1:] if not a.startswith("--")}
    known = {name for _, _, mods in REPOS for name in mods}
    unknown = wanted - known
    if unknown:
        print(f"unknown mods: {', '.join(sorted(unknown))} (known: {', '.join(sorted(known))})")
        return 2
    live = mods_dir()
    failed = False
    for folder, url, mods in REPOS:
        todo = {n: p for n, p in mods.items() if n in wanted or os.path.isdir(os.path.join(live, n))}
        if not todo:
            continue
        if not dry:
            err = pull(folder, url)
            if err:
                print(f"{folder}: pull failed, its mods are left as they are: {err}")
                failed = True
                continue
        for name, rel in todo.items():
            source = os.path.join(SRC, folder, rel)
            target = os.path.join(live, name)
            if not os.path.isdir(source):
                print(f"{name}: not in {folder} ({rel})")
                failed = True
                continue
            if not changes(target, source):
                print(f"{name}: up to date")
                continue
            old = (read_json(os.path.join(target, "mod.json")) or {}).get("version", "-")
            new = (read_json(os.path.join(source, "mod.json")) or {}).get("version", "-")
            if dry:
                print(f"{name}: would update ({old} -> {new})")
                continue
            backup = install(name, source, target)
            problem = check(target)
            print(f"{name}: updated ({old} -> {new})" + (f", old copy in {backup}" if backup else ""))
            if problem:
                print(f"{name}: herdr-app check failed:\n{problem}")
                failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

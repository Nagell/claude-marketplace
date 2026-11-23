#!/usr/bin/env python3
"""Find and run the repo's own lint, typecheck, format and test commands.

Two subcommands, stdlib only, no LLM.

``detect`` finds the commands for the files an MR changes. Manifests and
config are read as they are at ``--base`` (``git show``), so an MR cannot
change which commands run. A manifest that is new in the MR is listed under
``untrusted`` and never run. A package.json script runs by name, so the package
manager reads its body at head: when the body of a detected script, or of any
script it runs by name (pre/post hooks included), differs between base and
head, the script is listed under ``untrusted`` with the reason "script body
changed in this MR" and never run. A package whose package manager config
(.npmrc, .yarnrc(.yml), .pnpmfile.cjs, pnpm-workspace.yaml) changes in the MR,
or that has node_modules committed, is listed under ``untrusted`` with the
reason and none of its commands runs. A script that reaches a fix flag through
a script it runs by name is skipped. Prints a JSON plan:

  {"commands": [{"id", "kind", "cwd", "argv", "files", "source", "needs"}],
   "untrusted": [{"manifest", "commands", "reason"?}],
   "skipped": [{"source", "reason"}]}

``kind`` is ``lint``, ``format``, ``typecheck`` or ``test``. ``needs`` names
what must exist in the worktree for the command to run (``node_modules``).

``run`` executes a plan in the review worktree: 120 s per command, 300 s in
total, no fix flags, no installs. Each command runs in its own session (a
timeout kills the whole process group) with an allowlisted environment (PATH,
LANG, CI, NO_COLOR, HOME/XDG/TMPDIR under ``--tmp``, package manager cache and
offline settings) and, where ``unshare -rn`` works, with the network cut; the
JSON says ``"network": "cut"`` or ``"not cut"``. A command whose dependencies
are missing is skipped with "dependencies not installed"; a pytest or mypy
run that fails on an import error with no project venv is "not run: missing
dependencies". A timeout is "not run", never a
failure. A failing command is re-run at ``--base`` in a throwaway worktree
under ``--tmp`` (removed afterwards), and only messages that are not also
present there become findings. A failing test is re-run once at head first,
to rule out a flaky test. Head runs stop a quarter of the total limit early
(at most one per-command limit), so a base re-run always gets time. When the
base re-run times out or errors, or the base worktree cannot be made, the
command is "base run failed" with the reason and makes no finding. Prints:

  {"results": [...], "findings": [{"id": "check-1", "severity", "command",
   "messages"}], "pre_existing": [...], "not_run": [...],
   "base_worktree": <path or null>, "network": "cut" | "not cut",
   "error": <only when git worktree add failed>}

Messages are compared as counts after dropping paths, line and column
numbers and timings, so a moved error is not new and a second copy is.
"""

from __future__ import annotations

import argparse
import collections
import fnmatch
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path, PurePosixPath

NODE_SCRIPTS = {
    "lint": "lint", "typecheck": "typecheck", "type-check": "typecheck",
    "check": "typecheck", "format:check": "format", "test": "test",
    "test:unit": "test",
}
LOCKFILES = [
    ("pnpm-lock.yaml", "pnpm"), ("yarn.lock", "yarn"), ("bun.lock", "bun"),
    ("bun.lockb", "bun"), ("package-lock.json", "npm"),
]
ESLINT_CONFIGS = ("eslint.config.js", "eslint.config.mjs", "eslint.config.cjs",
                  "eslint.config.ts", ".eslintrc", ".eslintrc.js", ".eslintrc.cjs",
                  ".eslintrc.json", ".eslintrc.yml", ".eslintrc.yaml")
PRETTIER_CONFIGS = (".prettierrc", ".prettierrc.json", ".prettierrc.yml",
                    ".prettierrc.yaml", ".prettierrc.js", ".prettierrc.cjs",
                    ".prettierrc.mjs", "prettier.config.js", "prettier.config.cjs",
                    "prettier.config.mjs")
JS_EXT = (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".vue", ".svelte")
FIX_FLAGS = {"--fix": None, "--write": "--check", "-w": None}
SHELL_OPS = re.compile(r"&&|\|\||[|;<>`$]")
# package manager config that changes what a script runs (script-shell, hooks, ...)
PM_CONFIGS = (".npmrc", ".yarnrc", ".yarnrc.yml", ".pnpmfile.cjs", "pnpm-workspace.yaml")
PY_TOOLS = ("pytest", "mypy")
IMPORT_ERROR = re.compile(r"ModuleNotFoundError|ImportError|No module named|\[import-not-found\]")
PER_COMMAND = 120
TOTAL = 300
BASE_RESERVE = 0.25  # share of TOTAL kept back from head runs for base re-runs


# ---------------------------------------------------------------- git helpers

def git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)


class Snapshot:
    """Files of the repo at one commit."""

    def __init__(self, repo: Path, ref: str):
        self.repo, self.ref = repo, ref
        out = git(repo, "ls-tree", "-r", "--name-only", ref)
        if out.returncode != 0:
            sys.exit(f"git ls-tree {ref} failed: {out.stderr.strip()}")
        self.files = set(out.stdout.splitlines())

    def has(self, rel: str) -> bool:
        return rel in self.files

    def read(self, rel: str) -> str:
        return git(self.repo, "show", f"{self.ref}:{rel}").stdout


def join(d: str, name: str) -> str:
    return name if d in ("", ".") else f"{d}/{name}"


def parents(path: str) -> list[str]:
    """The file's directory and every parent, nearest first, ending at '.'."""
    p = PurePosixPath(path).parent
    return [p.as_posix(), *[q.as_posix() for q in p.parents]]


def nearest(snap: Snapshot, path: str, name: str) -> str | None:
    for d in parents(path):
        if snap.has(join(d, name)):
            return d
    return None


def rel_to(path: str, root: str) -> str:
    return path if root == "." else path[len(root) + 1:]


# ------------------------------------------------------------------- detect

def changed_files(repo: Path, base: str, head: str) -> list[str]:
    out = git(repo, "diff", "--name-only", "--diff-filter=d", base, head)
    return [f for f in out.stdout.splitlines() if f]


def strip_fix(script: str) -> tuple[list[str] | None, str]:
    """Check-only argv for a script with a fix flag, or None and why not."""
    if SHELL_OPS.search(script):
        return None, "script uses a fix flag inside a compound command; skipped"
    tokens = shlex.split(script)
    out = []
    for t in tokens:
        flag = t.split("=", 1)[0]  # "--fix" and "--fix=true" alike
        if flag in FIX_FLAGS:
            if FIX_FLAGS[flag]:
                out.append(FIX_FLAGS[flag])
            continue
        out.append(t)
    return out, "fix flag removed"


def has_fix_flag(script: str) -> bool:
    return any(re.search(rf"(^|\s){re.escape(f)}(\s|=|$)", script) for f in FIX_FLAGS)


def package_manager(snap: Snapshot, root: str) -> str:
    for d in parents(join(root, "x")):  # the project root, then up to the repo root
        for lock, pm in LOCKFILES:
            if snap.has(join(d, lock)):
                return pm
    return "pnpm"


def scripts_reached(name: str, scripts: dict) -> set[str]:
    """``name`` plus every script it may run by name: its pre/post hooks and
    any script named (or matched by a ``*`` pattern) in a body, transitively."""
    seen: set[str] = set()
    todo = [name]
    while todo:
        n = todo.pop()
        if n in seen:
            continue
        seen.add(n)
        todo += [h for h in (f"pre{n}", f"post{n}") if h in scripts]
        body = str(scripts.get(n, ""))
        for t in re.split(r"[\s&|;()'\"]+", body):
            if t in scripts:
                todo.append(t)
            elif "*" in t:
                todo += [s for s in scripts if fnmatch.fnmatchcase(s, t)]
    return seen


def changed_scripts(name: str, base_scripts: dict, head_scripts: dict) -> list[str]:
    """Scripts ``name`` may run whose body differs between base and head."""
    reached = scripts_reached(name, base_scripts) | scripts_reached(name, head_scripts)
    return sorted(n for n in reached if base_scripts.get(n) != head_scripts.get(n))


def package_untrusted(base: Snapshot, head: Snapshot, root: str) -> str | None:
    """Why the package's commands must not run at all, or None."""
    dirs = parents(join(root, "x"))  # the project root, then up to the repo root
    for d in dirs:
        for name in PM_CONFIGS:
            rel = join(d, name)
            if base.has(rel) != head.has(rel) or (base.has(rel) and base.read(rel) != head.read(rel)):
                return f"package manager config changed in this MR: {rel}"
    prefixes = tuple(join(d, "node_modules/") for d in dirs)
    if any(f.startswith(prefixes) for f in head.files):
        return "node_modules is committed to the repo"
    return None


def exec_argv(pm: str, argv: list[str]) -> list[str]:
    """Run a tool from node_modules: never install it, and keep its flags away from npm."""
    if pm == "npm":
        return ["npm", "exec", "--no", "--", *argv]
    return [pm, "exec", *argv]


def list_changed_script(plan: dict, manifest: str, name: str) -> None:
    reason = "script body changed in this MR"
    entry = next((u for u in plan["untrusted"]
                  if u["manifest"] == manifest and u.get("reason") == reason), None)
    if entry is None:
        entry = {"manifest": manifest, "commands": [], "reason": reason}
        plan["untrusted"].append(entry)
    entry["commands"].append(f"run {name}")


def detect_node(base: Snapshot, head: Snapshot, files: list[str], plan: dict) -> None:
    roots: dict[str, list[str]] = {}
    for f in files:
        root = nearest(base, f, "package.json")
        head_root = nearest(head, f, "package.json")
        if head_root is not None and head_root != root:
            # a manifest the MR adds: list it, never run it
            manifest = join(head_root, "package.json")
            if not any(u["manifest"] == manifest for u in plan["untrusted"]):
                try:
                    scripts = json.loads(head.read(manifest)).get("scripts", {})
                except ValueError:
                    scripts = {}
                plan["untrusted"].append({
                    "manifest": manifest,
                    "commands": [f"run {n}" for n in scripts if n in NODE_SCRIPTS]})
            continue
        if root is not None:
            roots.setdefault(root, []).append(f)
    for root, rfiles in sorted(roots.items()):
        manifest = join(root, "package.json")
        try:
            pkg = json.loads(base.read(manifest))
        except ValueError:
            plan["skipped"].append({"source": manifest, "reason": "package.json is not valid JSON"})
            continue
        pm = package_manager(base, root)
        scripts = pkg.get("scripts", {}) or {}
        try:
            head_scripts = json.loads(head.read(manifest)).get("scripts", {}) or {}
        except ValueError:
            head_scripts = {}
        why_not = package_untrusted(base, head, root)
        if why_not:
            plan["untrusted"].append({"manifest": manifest, "reason": why_not,
                                      "commands": [f"run {n}" for n in NODE_SCRIPTS
                                                   if n in scripts]})
            continue
        for name, kind in NODE_SCRIPTS.items():
            if name not in scripts:
                continue
            if changed_scripts(name, scripts, head_scripts):
                # the package manager runs the head body, so a changed one never runs
                list_changed_script(plan, manifest, name)
                continue
            body = str(scripts[name])
            source = f"{manifest} scripts.{name}"
            if any(has_fix_flag(str(scripts.get(n, "")))
                   for n in scripts_reached(name, scripts) - {name}):
                plan["skipped"].append({"source": source,
                                        "reason": "a script it runs uses a fix flag; skipped"})
                continue
            if has_fix_flag(body):
                argv, why = strip_fix(body)
                if argv is None:
                    plan["skipped"].append({"source": source, "reason": why})
                    continue
                add(plan, kind, root, exec_argv(pm, argv), [], source + " (fix flag removed)",
                    "node_modules")
                continue
            add(plan, kind, root, [pm, "run", name], [], source, "node_modules")
        js = [rel_to(f, root) for f in rfiles if f.endswith(JS_EXT)]
        if not js:
            continue
        if "lint" not in scripts and any(base.has(join(root, c)) for c in ESLINT_CONFIGS):
            add(plan, "lint", root, ["node_modules/.bin/eslint", *js], js,
                f"{root}/eslint config", "node_modules")
        has_prettier = any(base.has(join(root, c)) for c in PRETTIER_CONFIGS) or "prettier" in pkg
        if "format:check" not in scripts and has_prettier:
            add(plan, "format", root, ["node_modules/.bin/prettier", "--check", *js], js,
                f"{root}/prettier config", "node_modules")


def py_config(base: Snapshot, root: str) -> dict[str, bool]:
    pyproject = base.read(join(root, "pyproject.toml")) if base.has(join(root, "pyproject.toml")) else ""
    setup_cfg = base.read(join(root, "setup.cfg")) if base.has(join(root, "setup.cfg")) else ""
    return {
        "ruff": "[tool.ruff" in pyproject or base.has(join(root, "ruff.toml"))
        or base.has(join(root, ".ruff.toml")),
        "mypy": "[tool.mypy" in pyproject or base.has(join(root, "mypy.ini"))
        or "[mypy" in setup_cfg,
        "pytest": "[tool.pytest" in pyproject or base.has(join(root, "pytest.ini"))
        or "[tool:pytest" in setup_cfg,
    }


def list_untrusted(base: Snapshot, head: Snapshot, f: str, name: str, plan: dict,
                   commands) -> bool:
    """List a manifest the MR adds next to ``f``; True when one was found."""
    head_root = nearest(head, f, name)
    if head_root is None or head_root == nearest(base, f, name):
        return False
    manifest = join(head_root, name)
    if not any(u["manifest"] == manifest for u in plan["untrusted"]):
        plan["untrusted"].append({"manifest": manifest, "commands": commands(manifest)})
    return True


def py_commands(head: Snapshot):
    def commands(manifest: str) -> list[str]:
        text = head.read(manifest)
        return [c for key, c in (("[tool.ruff", "ruff check"), ("[tool.mypy", "mypy"),
                                 ("[tool.pytest", "pytest")) if key in text]
    return commands


def detect_python(base: Snapshot, head: Snapshot, files: list[str], plan: dict) -> None:
    py = [f for f in files if f.endswith(".py")]
    roots: dict[str, list[str]] = {}
    for f in py:
        if list_untrusted(base, head, f, "pyproject.toml", plan, py_commands(head)):
            continue
        root = next((d for d in parents(f)
                     if any(base.has(join(d, n)) for n in
                            ("pyproject.toml", "ruff.toml", ".ruff.toml", "mypy.ini",
                             "pytest.ini", "setup.cfg"))), None)
        if root is not None:
            roots.setdefault(root, []).append(f)
    for root, rfiles in sorted(roots.items()):
        cfg = py_config(base, root)
        rel = [rel_to(f, root) for f in rfiles]
        if cfg["ruff"]:
            add(plan, "lint", root, ["ruff", "check", *rel], rel, f"{root} ruff config", "ruff")
            add(plan, "format", root, ["ruff", "format", "--check", *rel], rel,
                f"{root} ruff config", "ruff")
        if cfg["mypy"]:
            add(plan, "typecheck", root, ["mypy", *rel], rel, f"{root} mypy config", "mypy")
        if cfg["pytest"]:
            add(plan, "test", root, ["pytest", "-q"], [], f"{root} pytest config", "pytest")


def detect_go(base: Snapshot, head: Snapshot, files: list[str], plan: dict) -> None:
    mods: dict[str, set[str]] = {}
    for f in files:
        if not f.endswith(".go"):
            continue
        if list_untrusted(base, head, f, "go.mod", plan, lambda m: ["go vet", "go test"]):
            continue
        root = nearest(base, f, "go.mod")
        if root is not None:
            pkg = PurePosixPath(rel_to(f, root)).parent.as_posix()
            mods.setdefault(root, set()).add("./" + ("" if pkg == "." else pkg))
    for root, pkgs in sorted(mods.items()):
        pk = sorted(p.rstrip("/") or "." for p in pkgs)
        add(plan, "lint", root, ["go", "vet", *pk], pk, join(root, "go.mod"), "go")
        add(plan, "test", root, ["go", "test", *pk], pk, join(root, "go.mod"), "go")


def detect_rust(base: Snapshot, head: Snapshot, files: list[str], plan: dict) -> None:
    rs = [f for f in files if f.endswith(".rs") and not list_untrusted(
        base, head, f, "Cargo.toml", plan, lambda m: ["cargo check", "cargo test"])]
    roots = sorted({r for f in rs
                    for r in [nearest(base, f, "Cargo.toml")] if r is not None})
    for root in roots:
        add(plan, "typecheck", root, ["cargo", "check"], [], join(root, "Cargo.toml"), "cargo")
        add(plan, "test", root, ["cargo", "test"], [], join(root, "Cargo.toml"), "cargo")


def detect_shell(head: Snapshot, files: list[str], plan: dict) -> None:
    def is_shell(f: str) -> bool:
        if f.endswith((".sh", ".bash")):
            return True
        if "." in PurePosixPath(f).name:
            return False
        first = head.read(f).split("\n", 1)[0]
        return first.startswith("#!") and bool(re.search(r"\b(ba|da)?sh\b", first))

    sh = [f for f in files if is_shell(f)]
    if sh:
        add(plan, "lint", ".", ["shellcheck", *sh], sh, "shell files", "shellcheck")


def add(plan: dict, kind: str, cwd: str, argv: list[str], files: list[str], source: str,
        needs: str) -> None:
    plan["commands"].append({"id": f"cmd-{len(plan['commands']) + 1}", "kind": kind,
                             "cwd": cwd, "argv": argv, "files": files,
                             "source": source, "needs": needs})


def detect(repo: Path, base_ref: str, head_ref: str, files: list[str] | None = None) -> dict:
    base, head = Snapshot(repo, base_ref), Snapshot(repo, head_ref)
    files = files if files is not None else changed_files(repo, base_ref, head_ref)
    files = [f for f in files if head.has(f)]
    plan: dict = {"base": base_ref, "head": head_ref, "commands": [], "untrusted": [],
                  "skipped": []}
    detect_node(base, head, files, plan)
    detect_python(base, head, files, plan)
    detect_go(base, head, files, plan)
    detect_rust(base, head, files, plan)
    detect_shell(head, files, plan)
    return plan


# ---------------------------------------------------------------------- run

def deps_missing(cmd: dict, tree: Path) -> str | None:
    need = cmd.get("needs")
    if need == "node_modules":
        cwd = tree / cmd["cwd"]
        for d in [cwd, *cwd.parents]:
            if (d / "node_modules").is_dir():
                return None
            if d == tree:
                break
        return "dependencies not installed (no node_modules in the review worktree)"
    if need and shutil.which(need) is None:
        return f"dependencies not installed ({need} not on PATH)"
    return None


def has_venv(tree: Path, cwd: str) -> bool:
    return bool(os.environ.get("VIRTUAL_ENV")) or any(
        (tree / d / ".venv").is_dir() for d in {".", cwd})


def check_env(tmp: Path) -> dict:
    """An allowlisted environment: no tokens, no SSH agent, HOME inside ``tmp``."""
    real_home = Path.home()
    home = tmp / "home"
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "LANG": os.environ.get("LANG", "C.UTF-8"),
        "HOME": str(home), "TMPDIR": str(tmp / "tmp"),
        "XDG_CONFIG_HOME": str(home / ".config"), "XDG_CACHE_HOME": str(home / ".cache"),
        "XDG_DATA_HOME": str(home / ".local/share"), "XDG_STATE_HOME": str(home / ".local/state"),
        "CI": "1", "NO_COLOR": "1", "TERM": "dumb",
        # package managers: own caches, offline, never install
        "npm_config_cache": str(home / ".npm"), "npm_config_yes": "false",
        "npm_config_offline": "true", "YARN_CACHE_FOLDER": str(home / ".yarn-cache"),
        "GOPROXY": "off", "GOTOOLCHAIN": "local", "CARGO_NET_OFFLINE": "true",
        # installed toolchains and module caches are only found through these
        "GOPATH": os.environ.get("GOPATH", str(real_home / "go")),
        "CARGO_HOME": os.environ.get("CARGO_HOME", str(real_home / ".cargo")),
        "RUSTUP_HOME": os.environ.get("RUSTUP_HOME", str(real_home / ".rustup")),
    }
    for name in ("GOMODCACHE", "VIRTUAL_ENV", "LC_ALL"):
        if os.environ.get(name):
            env[name] = os.environ[name]
    for key in ("HOME", "TMPDIR", "XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_DATA_HOME",
                "XDG_STATE_HOME"):
        Path(env[key]).mkdir(parents=True, exist_ok=True)
    return env


def network_cut() -> list[str]:
    """``unshare -rn`` when it works here, else nothing."""
    if shutil.which("unshare") is None:
        return []
    try:
        ok = subprocess.run(["unshare", "-rn", "true"], capture_output=True,
                            timeout=10).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        ok = False
    return ["unshare", "-rn"] if ok else []


def execute(argv: list[str], cwd: Path, timeout: float, env: dict) -> dict:
    start = time.monotonic()
    try:
        # own session, so a timeout kills the whole process group, test-runner children too
        proc = subprocess.Popen(argv, cwd=cwd, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                env=env, start_new_session=True)
    except OSError as e:
        return {"status": "error", "exit": None, "output": str(e), "seconds": 0.0}
    try:
        out, _ = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.communicate()
        return {"status": "timeout", "seconds": round(time.monotonic() - start, 1)}
    return {"status": "pass" if proc.returncode == 0 else "fail", "exit": proc.returncode,
            "output": out or "", "seconds": round(time.monotonic() - start, 1)}


NOISE = [
    (re.compile(r"\x1b\[[0-9;]*[A-Za-z]"), ""),           # colour codes
    (re.compile(r"\(\d+,\d+\)"), ""),                       # (line,col), tsc
    (re.compile(r"^\s*\d+(:\d+)?(?=\s)"), ""),               # leading line:col, eslint stylish
    (re.compile(r"(:\d+)+(?=[:\s)]|$)"), ""),              # :line:col
    (re.compile(r"\b\d+(\.\d+)?\s*(ms|s|sec|seconds)\b"), "<t>"),  # durations
    (re.compile(r"0x[0-9a-f]+"), "<addr>"),
    (re.compile(r"\s+"), " "),
]


def normalise(output: str, roots: list[Path]) -> collections.Counter:
    """Messages with paths, positions and timings removed, counted, so a second
    copy of an error that exists once at base still counts as new."""
    msgs: collections.Counter = collections.Counter()
    for line in output.splitlines():
        for r in roots:
            line = line.replace(str(r) + os.sep, "").replace(str(r), "")
        for rx, sub in NOISE:
            line = rx.sub(sub, line)
        line = line.strip()
        if line:
            msgs[line] += 1
    return msgs


def tail(text: str, n: int = 40) -> str:
    return "\n".join(text.splitlines()[-n:])


def make_base_worktree(repo: Path, base: str, tmp: Path) -> Path:
    wt = tmp / "checks-base"
    out = git(repo, "worktree", "add", "--detach", str(wt), base)
    if out.returncode != 0:
        raise RuntimeError(f"git worktree add failed: {out.stderr.strip()}")
    return wt


def link_deps(head_tree: Path, base_tree: Path, cwd: str) -> None:
    """Share installed dependencies with the base worktree, read-only use."""
    for d in {".", cwd}:
        for name in ("node_modules", ".venv"):
            src, dst = head_tree / d / name, base_tree / d / name
            if src.is_dir() and not dst.exists() and dst.parent.is_dir():
                dst.symlink_to(src, target_is_directory=True)


def run(plan: dict, repo: Path, tmp: Path, per_command: float = PER_COMMAND,
        total: float = TOTAL, wrap: list[str] | None = None,
        skip_deps_check: bool = False) -> dict:
    tmp.mkdir(parents=True, exist_ok=True)
    env = check_env(tmp)
    net = network_cut()
    deadline = time.monotonic() + total
    # head runs stop this much before the deadline, so a base re-run always has time
    reserve = min(per_command, total * BASE_RESERVE)
    report: dict = {"results": [], "findings": [], "pre_existing": [], "not_run": [],
                    "base_worktree": None, "network": "cut" if net else "not cut"}
    base_wt: Path | None = None
    base_error: str | None = None

    def left() -> float:
        return deadline - time.monotonic()

    def go(cmd: dict, tree: Path, keep: float = 0.0) -> dict:
        budget = min(per_command, left() - keep)
        if budget <= 0:
            return {"status": "timeout", "seconds": 0.0, "reason": "total time limit"}
        return execute([*net, *(wrap or []), *cmd["argv"]], tree / cmd["cwd"], budget, env)

    def base_failed(res: dict, cmd: dict, why: str) -> None:
        reason = f"base run failed: {why}"
        res.update(status="base_run_failed", reason=reason)
        report["not_run"].append({"id": cmd["id"], "reason": reason})

    try:
        for cmd in plan["commands"]:
            res = {"id": cmd["id"], "kind": cmd["kind"], "cwd": cmd["cwd"],
                   "argv": cmd["argv"], "source": cmd["source"]}
            report["results"].append(res)
            missing = None if skip_deps_check else deps_missing(cmd, repo)
            if missing:
                res.update(status="skipped", reason=missing)
                report["not_run"].append({"id": cmd["id"], "reason": missing})
                continue
            head = go(cmd, repo, reserve)
            if head["status"] == "timeout":
                res.update(status="not_run", reason="not run: timed out")
                report["not_run"].append({"id": cmd["id"], "reason": "not run: timed out"})
                continue
            res["head"] = {"exit": head.get("exit"), "output_tail": tail(head.get("output", ""))}
            if head["status"] == "pass":
                res["status"] = "pass"
                continue
            if (cmd.get("needs") in PY_TOOLS and not has_venv(repo, cmd["cwd"])
                    and IMPORT_ERROR.search(head.get("output", ""))):
                reason = "not run: missing dependencies (no project venv)"
                res.update(status="not_run", reason=reason)
                report["not_run"].append({"id": cmd["id"], "reason": reason})
                continue
            if cmd["kind"] == "test":
                again = go(cmd, repo, reserve)
                if again["status"] == "pass":
                    res.update(status="flaky", reason="failed once, passed on re-run")
                    continue
            if base_wt is None and base_error is None:
                try:
                    base_wt = make_base_worktree(repo, plan["base"], tmp)
                    report["base_worktree"] = str(base_wt)
                except RuntimeError as e:
                    base_error = str(e)
                    report["error"] = base_error
            if base_wt is None:
                base_failed(res, cmd, base_error or "no base worktree")
                continue
            link_deps(repo, base_wt, cmd["cwd"])
            base_cmd = dict(cmd, argv=[a for a in cmd["argv"]
                                       if a not in cmd["files"]
                                       or (base_wt / cmd["cwd"] / a).exists()])
            if cmd["files"] and not [a for a in base_cmd["argv"] if a in cmd["files"]]:
                base = {"status": "pass", "exit": 0, "output": "",
                        "note": "no changed file exists at base"}
            else:
                base = go(base_cmd, base_wt)
            res["base"] = {"exit": base.get("exit"), "status": base["status"],
                           "output_tail": tail(base.get("output", ""))}
            if base["status"] == "timeout":
                base_failed(res, cmd, base.get("reason", "timed out"))
                continue
            if base["status"] == "error":
                base_failed(res, cmd, base.get("output", "error"))
                continue
            roots = [repo, base_wt, tmp]
            head_msgs = normalise(head.get("output", ""), roots)
            base_msgs = (normalise(base.get("output", ""), roots) if base["status"] == "fail"
                         else collections.Counter())
            new = sorted((head_msgs - base_msgs).elements())
            if base["status"] == "fail" and not new:
                res["status"] = "pre_existing"
                report["pre_existing"].append({"id": cmd["id"], "argv": cmd["argv"]})
                continue
            res["status"] = "fail"
            report["findings"].append({
                "id": f"check-{len(report['findings']) + 1}",
                "severity": "medium" if cmd["kind"] in ("test", "typecheck") else "low",
                "kind": cmd["kind"], "command": shlex.join(cmd["argv"]), "cwd": cmd["cwd"],
                "messages": new[:30] or [tail(head.get("output", ""), 20)]})
    finally:
        if base_wt is not None:
            git(repo, "worktree", "remove", "--force", str(base_wt))
            git(repo, "worktree", "prune")
            report["base_worktree_removed"] = not base_wt.exists()
    return report


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("detect", help="find the check commands for the changed files")
    d.add_argument("--repo", required=True, help="the review worktree")
    d.add_argument("--base", required=True, help="base_sha")
    d.add_argument("--head", required=True, help="head_sha")
    d.add_argument("--paths-file", default=None,
                   help="changed paths, one per line (default: git diff base head)")
    r = sub.add_parser("run", help="run a detect plan")
    r.add_argument("--plan", required=True, help="the JSON detect printed")
    r.add_argument("--repo", required=True, help="the review worktree, at head")
    r.add_argument("--tmp", required=True, help="a folder under the run's temp dir")
    r.add_argument("--per-command", type=float, default=PER_COMMAND)
    r.add_argument("--total", type=float, default=TOTAL)
    r.add_argument("--wrap", default=None,
                   help="prefix every command with this, when the machine notes say how")
    r.add_argument("--skip-deps-check", action="store_true",
                   help="run even without node_modules, when the machine notes say how")
    a = ap.parse_args()
    repo = Path(a.repo).resolve()
    if a.cmd == "detect":
        files = None
        if a.paths_file:
            files = [x.strip() for x in Path(a.paths_file).read_text().splitlines() if x.strip()]
        print(json.dumps(detect(repo, a.base, a.head, files), indent=2))
        return
    plan = json.loads(Path(a.plan).read_text())
    out = run(plan, repo, Path(a.tmp).resolve(), a.per_command, a.total,
              shlex.split(a.wrap) if a.wrap else None, a.skip_deps_check)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()

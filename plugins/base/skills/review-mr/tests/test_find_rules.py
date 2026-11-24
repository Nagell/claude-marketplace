import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import find_rules  # noqa: E402


def write(folder: Path, name: str, text: str) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    p = folder / name
    p.write_text(text, encoding="utf-8")
    return p


def git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def run_script(cwd: Path, rules: Path) -> dict:
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "find_rules.py")], cwd=cwd,
        capture_output=True, text=True, check=True,
        env={"REVIEW_RULES_DIR": str(rules), "PATH": "/usr/bin:/bin:/usr/local/bin"},
    )
    return json.loads(proc.stdout)


@pytest.mark.parametrize("url,name", [
    ("git@gitlab.com:group/sub/provetcloud.git", "provetcloud"),
    ("https://gitlab.com/group/provet-cloud-frontend.git", "provet-cloud-frontend"),
    ("https://github.com/Nagell/claude-marketplace", "claude-marketplace"),
    ("https://github.com/Nagell/claude-marketplace/\n", "claude-marketplace"),
    ("/srv/git/repo.git", "repo"),
])
def test_repo_name_from_url(url, name):
    assert find_rules.repo_name_from_url(url) == name


def test_exact_name_wins_over_applies_to(tmp_path):
    exact = write(tmp_path, "app.md", "---\napplies-to: [other]\n---\n")
    write(tmp_path, "aaa.md", "---\napplies-to: [app]\n---\n")
    r = find_rules.find("app", tmp_path)
    assert r["path"] == str(exact)
    assert r["matched_by"] == "name"


def test_applies_to_flow_list(tmp_path):
    f = write(tmp_path, "shared.md", "---\napplies-to: [backend, 'frontend']\n---\n# body\n")
    r = find_rules.find("frontend", tmp_path)
    assert (r["path"], r["matched_by"]) == (str(f), "applies-to")
    assert r["expected"] == str(tmp_path / "frontend.md")


def test_applies_to_block_list(tmp_path):
    f = write(tmp_path, "shared.md", "---\nname: x\napplies-to:\n  - backend\n  - frontend\n---\n")
    assert find_rules.find("backend", tmp_path)["path"] == str(f)


def test_applies_to_block_list_at_column_zero(tmp_path):
    f = write(tmp_path, "shared.md", "---\napplies-to:\n- backend\n- frontend\n---\n")
    assert find_rules.find("frontend", tmp_path)["path"] == str(f)


def test_name_only_rules_files_are_not_reported_as_skipped(tmp_path):
    write(tmp_path, "frontend.md", "# Frontend rules\n")
    r = find_rules.find("backend", tmp_path)
    assert r["path"] is None and r["skipped"] == []


def test_body_is_never_read(tmp_path):
    write(tmp_path, "shared.md", "---\ntitle: x\n---\napplies-to: [app]\n")
    r = find_rules.find("app", tmp_path)
    assert r["path"] is None


def test_no_match(tmp_path):
    write(tmp_path, "shared.md", "---\napplies-to: [backend]\n---\n")
    r = find_rules.find("unknown", tmp_path)
    assert r == {"repo": "unknown", "path": None,
                 "expected": str(tmp_path / "unknown.md"),
                 "matched_by": None, "skipped": []}


def test_missing_rules_folder(tmp_path):
    r = find_rules.find("app", tmp_path / "nope")
    assert r["path"] is None and r["skipped"] == []


@pytest.mark.parametrize("text,reason", [
    ("---\napplies-to: [app]\n", "never closed"),
    ("---\napplies-to: [app\n---\n", "not closed with ]"),
    ("---\napplies-to:\n---\n", "is empty"),
])
def test_malformed_frontmatter_is_skipped_and_reported(tmp_path, text, reason):
    bad = write(tmp_path, "bad.md", text)
    good = write(tmp_path, "good.md", "---\napplies-to: [app]\n---\n")
    r = find_rules.find("app", tmp_path)
    assert r["path"] == str(good)
    assert r["skipped"][0]["path"] == str(bad)
    assert reason in r["skipped"][0]["reason"]


def test_worktree_uses_remote_name_not_directory(tmp_path):
    repo = tmp_path / "checkout-dir"
    repo.mkdir()
    git("init", "-q", "-b", "main", cwd=repo)
    git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q",
        "--allow-empty", "-m", "init", cwd=repo)
    git("remote", "add", "origin", "git@gitlab.com:group/provet-cloud-frontend.git", cwd=repo)
    wt = tmp_path / "wt" / "some-feature"
    git("worktree", "add", "-q", "-b", "feat", str(wt), cwd=repo)
    rules = tmp_path / "rules"
    shared = write(rules, "provetcloud.md",
                   "---\napplies-to: [provetcloud, provet-cloud-frontend]\n---\n")

    for cwd in (repo, wt):
        r = run_script(cwd, rules)
        assert r["repo"] == "provet-cloud-frontend"
        assert r["path"] == str(shared)
        assert r["matched_by"] == "applies-to"


def test_no_origin_fails_with_a_clear_message(tmp_path):
    git("init", "-q", cwd=tmp_path)
    proc = subprocess.run([sys.executable, str(SCRIPTS / "find_rules.py")],
                          cwd=tmp_path, capture_output=True, text=True)
    assert proc.returncode != 0
    assert "no origin remote" in proc.stderr


def test_counterpart_flag(tmp_path):
    rules = tmp_path / "rules"
    write(rules, "solo.md", "# Review rules: solo\n\n## Size excludes\n\nx\n")
    write(rules, "pair.md", "# Review rules\n\n## Counterpart\n\nThe sibling is other.\n")
    repo = tmp_path / "repo"
    repo.mkdir()
    for name, want in (("solo", False), ("pair", True), ("none", False)):
        proc = subprocess.run(
            [sys.executable, str(SCRIPTS / "find_rules.py"), "--repo-name", name],
            capture_output=True, text=True, check=True,
            env={"REVIEW_RULES_DIR": str(rules), "PATH": "/usr/bin:/bin:/usr/local/bin"})
        assert json.loads(proc.stdout)["counterpart"] is want, name


@pytest.mark.parametrize("body,want", [
    ("## Counterpart\n\nx\n", True),
    ("  ## Counterpart ##\n", True),
    ("## Counterpart repo\n", False),
    ("### Counterpart\n", False),
    ("```markdown\n## Counterpart\n```\n", False),
    ("<!--\n## Counterpart\n-->\n", False),
    ("﻿# Rules\n\n## Counterpart\n", True),
])
def test_has_counterpart_heading_forms(tmp_path, body, want):
    p = write(tmp_path, "r.md", body)
    assert find_rules.has_counterpart(p) is want


def test_has_counterpart_survives_a_bad_byte(tmp_path):
    p = tmp_path / "r.md"
    p.write_bytes(b"caf\xe9\n\n## Counterpart\n")
    assert find_rules.has_counterpart(p) is True


def test_bom_before_frontmatter_still_matches(tmp_path):
    rules = tmp_path / "rules"
    write(rules, "shared.md", "﻿---\napplies-to: [a, b]\n---\n")
    assert find_rules.find("b", rules)["matched_by"] == "applies-to"


def test_unreadable_md_entry_is_skipped_not_fatal(tmp_path):
    rules = tmp_path / "rules"
    (rules / "aa-dir.md").mkdir(parents=True)
    write(rules, "zz.md", "---\napplies-to: [b]\n---\n")
    r = find_rules.find("b", rules)
    assert r["matched_by"] == "applies-to"
    assert r["skipped"] and "aa-dir.md" in r["skipped"][0]["path"]

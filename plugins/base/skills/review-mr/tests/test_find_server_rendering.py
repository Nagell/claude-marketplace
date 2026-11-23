import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import find_server_rendering  # noqa: E402


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    git(tmp_path, "init", "-q")
    git(tmp_path, "config", "user.email", "t@example.com")
    git(tmp_path, "config", "user.name", "t")
    return tmp_path


def write(repo: Path, rel: str, text: str) -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    git(repo, "add", rel)


def apps(repo: Path, ref: str | None = None) -> list[dict]:
    return find_server_rendering.find(repo, ref)["apps"]


@pytest.mark.parametrize(
    ("rel", "text", "expected"),
    [
        ("nuxt.config.ts", "export default defineNuxtConfig({\n  ssr: false,\n})\n", False),
        ("nuxt.config.ts", "export default defineNuxtConfig({\n  ssr: true,\n})\n", True),
        ("nuxt.config.ts", "export default defineNuxtConfig({})\n", True),
        ("nuxt.config.ts", "export default defineNuxtConfig({\n  ssr: process.env.SSR === '1',\n})\n",
         "unknown"),
        ("next.config.mjs", "export default {\n  output: 'export',\n}\n", False),
        ("next.config.js", "module.exports = { reactStrictMode: true }\n", True),
        ("next.config.ts", "export default {\n  output: \"standalone\",\n}\n", True),
    ],
)
def test_decides_per_config(repo: Path, rel: str, text: str, expected: object) -> None:
    write(repo, rel, text)
    [app] = apps(repo)
    assert app["renders_on_server"] == expected
    assert app["config"] == rel


def test_comment_mentioning_the_setting_decides_nothing(repo: Path) -> None:
    write(repo, "nuxt.config.ts",
          "export default defineNuxtConfig({\n  // see issue (ssr: false)\n})\n")
    [app] = apps(repo)
    assert app["renders_on_server"] is True
    assert "default" in app["evidence"]


def test_evidence_names_the_line(repo: Path) -> None:
    write(repo, "apps/web/nuxt.config.ts", "export default defineNuxtConfig({\n  ssr: false,\n})\n")
    [app] = apps(repo)
    assert app["root"] == "apps/web"
    assert app["evidence"].startswith("apps/web/nuxt.config.ts:2:")


def test_build_output_and_dependencies_are_skipped(repo: Path) -> None:
    write(repo, "node_modules/x/nuxt.config.ts", "export default {}\n")
    write(repo, ".nuxt/nuxt.config.ts", "export default {}\n")
    assert apps(repo) == []


def test_no_framework_means_no_apps(repo: Path) -> None:
    write(repo, "package.json", "{}\n")
    assert apps(repo) == []


def test_ref_reads_the_committed_config(repo: Path) -> None:
    write(repo, "nuxt.config.ts", "export default defineNuxtConfig({\n  ssr: false,\n})\n")
    git(repo, "commit", "-qm", "client only")
    head = git(repo, "rev-parse", "HEAD")
    (repo / "nuxt.config.ts").write_text("export default defineNuxtConfig({})\n")
    assert apps(repo, head)[0]["renders_on_server"] is False
    assert apps(repo)[0]["renders_on_server"] is True

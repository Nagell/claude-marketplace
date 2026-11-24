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
        ("next.config.mjs", "export default {\n  output: 'export',\n}\n", True),
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


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # a per-route or per-build setting does not decide the whole app
        ("export default defineNuxtConfig({\n  routeRules: {\n    '/admin/**': {\n      ssr: false,\n"
         "    },\n  },\n})\n", "unknown"),
        ("export default defineNuxtConfig({\n  $production: {\n    ssr: false,\n  },\n})\n", "unknown"),
        ("export default defineNuxtConfig({\n  routeRules: { '/a': { ssr: true } },\n  ssr: false,\n})\n",
         False),
        # block comments, comments without a space, one-line configs
        ("export default defineNuxtConfig({\n  /*\n  ssr: false,\n  */\n})\n", True),
        ("export default defineNuxtConfig({\n  ssr: true,// keep\n})\n", True),
        ("export default defineNuxtConfig({ ssr: false })\n", False),
        ("export default defineNuxtConfig({\n  ssr: false,\n  ssr: true,\n})\n", "unknown"),
        # a brace or the word inside a string decides nothing
        ("export default defineNuxtConfig({\n  app: { head: { title: '{ ssr: false }' } },\n})\n", True),
    ],
)
def test_only_the_top_level_setting_decides(repo: Path, text: str, expected: object) -> None:
    write(repo, "nuxt.config.ts", text)
    [app] = apps(repo)
    assert app["renders_on_server"] == expected, app["evidence"]


def test_one_line_next_config(repo: Path) -> None:
    write(repo, "next.config.js", "module.exports = { output: 'standalone' };\n")
    assert apps(repo)[0]["renders_on_server"] is True


def test_url_in_a_string_is_not_a_comment(repo: Path) -> None:
    write(repo, "nuxt.config.ts",
          "export default defineNuxtConfig({\n  site: 'https://x.test', ssr: false,\n})\n")
    assert apps(repo)[0]["renders_on_server"] is False

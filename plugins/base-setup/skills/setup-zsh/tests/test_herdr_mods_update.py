import importlib.util
import json
import os
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "assets", "herdr-app", "herdr-mods-update.py")
spec = importlib.util.spec_from_file_location("herdr_mods_update", SCRIPT)
u = importlib.util.module_from_spec(spec)
spec.loader.exec_module(u)


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


class Manifest(unittest.TestCase):
    def test_keeps_settings_and_takes_version_and_new_keys(self):
        old = {"version": "1.0.0", "place": "left", "markdown": "code"}
        new = {"version": "1.1.0", "place": "none", "title": "Better Files"}
        self.assertEqual(
            u.merged_manifest(old, new),
            {"version": "1.1.0", "place": "left", "markdown": "code", "title": "Better Files"},
        )

    def test_missing_or_broken_old_takes_new(self):
        self.assertEqual(u.merged_manifest(None, {"version": "2"}), {"version": "2"})


class Update(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = self.tmp.name
        self.src = os.path.join(root, "src")
        self.app = os.path.join(root, "app")
        self.backups = os.path.join(root, "backups")
        patches = [
            mock.patch.object(u, "SRC", self.src),
            mock.patch.object(u, "BACKUPS", self.backups),
            mock.patch.object(u, "REPOS", [("repo", "unused", {"m": "mods/m", "other": "mods/other"})]),
            mock.patch.object(u, "pull", lambda folder, url: None),
            mock.patch.object(u, "check", lambda target: None),
            mock.patch.dict(os.environ, {"HERDR_APP_HOME": self.app}),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(self.tmp.cleanup)
        write(os.path.join(self.src, "repo/mods/m/main.js"), "new code")
        write(os.path.join(self.src, "repo/mods/m/mod.json"), json.dumps({"version": "2.0.0", "place": "none"}))
        write(os.path.join(self.src, "repo/mods/other/main.js"), "other")
        self.live = os.path.join(self.app, "mods", "m")
        write(os.path.join(self.live, "main.js"), "old code")
        write(os.path.join(self.live, "stale.js"), "gone upstream")
        write(os.path.join(self.live, "mod.json"), json.dumps({"version": "1.0.0", "place": "left"}))
        write(os.path.join(self.live, "gpui-kit.d.ts"), "types")
        write(os.path.join(self.live, ".cache/x"), "cached")

    def test_updates_installed_mod_keeps_settings_and_backs_up(self):
        self.assertEqual(u.main([]), 0)
        self.assertEqual(read(os.path.join(self.live, "main.js")), "new code")
        self.assertFalse(os.path.exists(os.path.join(self.live, "stale.js")))
        manifest = json.loads(read(os.path.join(self.live, "mod.json")))
        self.assertEqual(manifest, {"version": "2.0.0", "place": "left"})
        (backup,) = os.listdir(self.backups)
        self.assertTrue(backup.startswith("m-1.0.0-"))
        self.assertEqual(read(os.path.join(self.backups, backup, "main.js")), "old code")

    def test_keeps_herdr_own_files(self):
        u.main([])
        self.assertEqual(read(os.path.join(self.live, "gpui-kit.d.ts")), "types")
        self.assertEqual(read(os.path.join(self.live, ".cache/x")), "cached")

    def test_herdr_own_files_alone_are_not_a_change(self):
        u.main([])
        write(os.path.join(self.live, "jsconfig.json"), "{}")
        with mock.patch.object(u, "install") as install:
            u.main([])
        install.assert_not_called()

    def test_leaves_mods_that_are_not_installed(self):
        u.main([])
        self.assertFalse(os.path.exists(os.path.join(self.app, "mods", "other")))

    def test_install_adds_a_named_mod(self):
        u.main(["--install", "other"])
        self.assertEqual(read(os.path.join(self.app, "mods", "other", "main.js")), "other")

    def test_second_run_is_up_to_date(self):
        u.main([])
        with mock.patch.object(u, "install") as install:
            u.main([])
        install.assert_not_called()

    def test_dry_run_changes_nothing(self):
        with mock.patch.object(u, "pull") as pull:
            u.main(["--dry-run"])
        pull.assert_not_called()
        self.assertEqual(read(os.path.join(self.live, "main.js")), "old code")
        self.assertFalse(os.path.exists(self.backups) and os.listdir(self.backups))

    def test_failed_pull_leaves_its_mods_alone(self):
        with mock.patch.object(u, "pull", lambda folder, url: "network down"):
            self.assertEqual(u.main([]), 1)
        self.assertEqual(read(os.path.join(self.live, "main.js")), "old code")

    def test_unknown_install_name_is_refused(self):
        self.assertEqual(u.main(["--install", "nope"]), 2)


if __name__ == "__main__":
    unittest.main()

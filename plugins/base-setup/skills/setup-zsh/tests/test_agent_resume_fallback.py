"""Run: python3 -I -B -m unittest discover -s plugins/base-setup/skills/setup-zsh/tests"""
import contextlib
import importlib.util
import io
import json
import os
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location(
    "fallback", os.path.join(HERE, "..", "assets", "herdr-app", "agent-resume-fallback.py"))
fallback = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fallback)

PROJECT = "/home/u/.claude/projects/-home-u-work"
OLD = "aaaaaaaa-0000-0000-0000-000000000001"
NEW = "bbbbbbbb-0000-0000-0000-000000000002"
OLDER = "cccccccc-0000-0000-0000-000000000003"


def terminal(session=NEW, project=PROJECT):
    label = {"agent": "claude", "session": session, "cwd": "/home/u/work",
             "transcript": f"{project}/{session}.jsonl", "pid": 200, "shell": 100,
             "boot": "old-boot", "at": 1, "args": ["--model", "opus"]}
    return {"address": "t1", "state": "live", "pid": 300,
            "labels": {"agent-resume": json.dumps(label, separators=(",", ":")), "where": "x"}}


def events(saved_at):
    return [
        {"at": "2026-11-12T23:00:00", "event": "hook", "agent": "claude", "terminal": "t1", "outcome": "saved"},
        {"at": "2026-11-12T23:55:13", "event": "watch", "terminal": "t1", "outcome": f"forgot {OLD}"},
        {"at": "2026-11-12T23:55:20", "event": "hook", "agent": "claude", "terminal": "t2", "outcome": "saved"},
        {"at": saved_at, "event": "hook", "agent": "claude", "terminal": "t1", "outcome": "saved"},
    ]


def hook(at):
    return {"at": at, "event": "hook", "agent": "claude", "terminal": "t1", "outcome": "saved"}


def forgot(at, session=OLD):
    return {"at": at, "event": "watch", "terminal": "t1", "outcome": f"forgot {session}"}


def files(*sessions):
    present = {f"{PROJECT}/{s}.jsonl" for s in sessions}
    return lambda path: path in present


class FallbackTest(unittest.TestCase):
    def test_restart_falls_back_to_replaced_session(self):
        found = fallback.fix(terminal(), events("2026-11-12T23:55:19"), "new-boot", files(OLD))
        self.assertIsNotNone(found)
        text, was, now = found
        self.assertEqual((was, now), (NEW, OLD))
        label = json.loads(text)
        expected = json.loads(terminal()["labels"]["agent-resume"])
        expected.update(session=OLD, transcript=f"{PROJECT}/{OLD}.jsonl")
        self.assertEqual(label, expected)
        self.assertEqual(list(label), list(expected))  # field order kept
        self.assertNotIn(" ", text)  # compact, like the mod writes it

    def test_deliberate_quit_is_left_alone(self):
        self.assertIsNone(fallback.fix(terminal(), events("2026-11-12T23:59:00"), "new-boot", files(OLD)))

    def test_label_with_transcript_is_left_alone(self):
        self.assertIsNone(fallback.fix(terminal(), events("2026-11-12T23:55:19"), "new-boot", files(OLD, NEW)))

    def test_agent_still_running_is_left_alone(self):
        live = terminal()
        live["pid"] = 100
        self.assertIsNone(fallback.fix(live, events("2026-11-12T23:55:19"), "old-boot", files(OLD)))

    def test_missing_old_transcript_is_left_alone(self):
        self.assertIsNone(fallback.fix(terminal(), events("2026-11-12T23:55:19"), "new-boot", files()))

    def test_no_boot_id_uses_shell_pid(self):
        # macOS without kern.boottime: only a different shell pid means the agent is lost
        self.assertIsNotNone(fallback.fix(terminal(), events("2026-11-12T23:55:19"), None, files(OLD)))
        same_shell = terminal()
        same_shell["pid"] = 100
        self.assertIsNone(fallback.fix(same_shell, events("2026-11-12T23:55:19"), None, files(OLD)))

    def test_second_saved_after_forgot_is_left_alone(self):
        log = [forgot("2026-11-12T23:55:00"), hook("2026-11-12T23:55:05"), hook("2026-11-12T23:55:10")]
        self.assertIsNone(fallback.fix(terminal(), log, "new-boot", files(OLD)))

    def test_saved_before_forgot_is_left_alone(self):
        # same second, so only the log order tells them apart
        log = [hook("2026-11-12T23:55:00"), forgot("2026-11-12T23:55:00")]
        self.assertIsNone(fallback.fix(terminal(), log, "new-boot", files(OLD)))

    def test_only_last_forgot_counts(self):
        log = [forgot("2026-11-12T23:00:00", OLDER), hook("2026-11-12T23:00:05"),
               forgot("2026-11-12T23:55:00"), hook("2026-11-12T23:55:05")]
        found = fallback.fix(terminal(), log, "new-boot", files(OLD, OLDER))
        self.assertEqual(found[1:], (NEW, OLD))

    def test_main_dry_run_reads_log_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as home:
            project = os.path.join(home, "project")
            os.makedirs(project)
            open(os.path.join(project, OLD + ".jsonl"), "w").close()
            data = os.path.join(home, "data", "agent-resume")
            os.makedirs(data)
            with open(os.path.join(data, "log.jsonl"), "w") as f:
                f.write("{not json\n")
                for event in events("2026-11-12T23:55:19"):
                    f.write(json.dumps(event) + "\n")
            calls = []

            def hc(*args, timeout):
                calls.append((args, timeout))
                if args[0] == "get":
                    return json.dumps(terminal(project=project))
                return ""

            out = io.StringIO()
            with mock.patch.dict(os.environ, {"HERDR_APP_HOME": home}), \
                    mock.patch.object(fallback, "hc", hc), contextlib.redirect_stdout(out):
                self.assertEqual(fallback.main(["agent-resume-fallback.py", "--dry-run", "t1"]), 0)
            self.assertEqual(json.loads(out.getvalue()), {
                "dry_run": True, "would_restore": [{"terminal": "t1", "from": NEW, "to": OLD}]})
            self.assertEqual(calls, [(("get", "t1", "--json"), 3)])  # no label, short timeout
            self.assertFalse(os.path.exists(os.path.join(data, "fallback.jsonl")))


if __name__ == "__main__":
    unittest.main()

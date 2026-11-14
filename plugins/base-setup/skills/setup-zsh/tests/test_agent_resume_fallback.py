"""Run: python3 -I -B -m unittest discover -s plugins/base-setup/skills/setup-zsh/tests"""
import importlib.util
import json
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location(
    "fallback", os.path.join(HERE, "..", "assets", "herdr-app", "agent-resume-fallback.py"))
fallback = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fallback)

PROJECT = "/home/u/.claude/projects/-home-u-work"
OLD = "aaaaaaaa-0000-0000-0000-000000000001"
NEW = "bbbbbbbb-0000-0000-0000-000000000002"


def terminal(session=NEW):
    label = {"agent": "claude", "session": session, "cwd": "/home/u/work",
             "transcript": f"{PROJECT}/{session}.jsonl", "pid": 200, "shell": 100,
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


if __name__ == "__main__":
    unittest.main()
